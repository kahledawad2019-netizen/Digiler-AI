"""ResourceRegistry — the orchestrator that gives a raw file an identity.

It is the single entry point for "the platform now knows about this file". On
``register`` it: computes file facts + SHA-256, mints a stable resource_id,
builds a validated ResourceMetadata, writes the JSON sidecar beside the file,
and upserts the Knowledge Catalog — recording an event for provenance.

It deliberately does NO extraction/embedding/graphing. Those are later phases;
the registry just tracks identity, version, hash, status, and relationships, so
the pipeline always knows what exists and what changed.
"""

from __future__ import annotations

import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ala.catalog.repository import KnowledgeCatalog
from ala.config.settings import Settings
from ala.core.clock import Clock, SystemClock
from ala.core.enums import (
    ChunkStrategy,
    DocType,
    Language,
    Persistence,
    ProcessingStatus,
    Role,
    StageStatus,
)
from ala.core.exceptions import (
    DuplicateResourceError,
    RegistryError,
    ValidationError,
)
from ala.core.hashing import sha256_file
from ala.core import ids
from ala.metadata.schema import (
    FileInfo,
    PedagogyInfo,
    ResourceMetadata,
    SourceInfo,
)
from ala.metadata.sidecar import write_sidecar
from ala.metadata.validation import ValidationContext, ValidationPipeline

log = logging.getLogger("ala.registry")

_CHUNK_BY_DOCTYPE = {
    DocType.LECTURE_SLIDES: ChunkStrategy.SLIDE,
    DocType.NOTEBOOK: ChunkStrategy.NOTEBOOK_CELL,
    DocType.VIDEO: ChunkStrategy.TRANSCRIPT_WINDOW,
    DocType.LESSON_PAGE: ChunkStrategy.SECTION,
    DocType.TEXTBOOK: ChunkStrategy.SECTION,
    DocType.REFERENCE: ChunkStrategy.SECTION,
    DocType.OVERVIEW_NOTE: ChunkStrategy.SECTION,
    DocType.WEB: ChunkStrategy.SECTION,
}


class ResourceRegistry:
    def __init__(
        self,
        settings: Settings,
        catalog: KnowledgeCatalog,
        validator: ValidationPipeline | None = None,
        clock: Clock | None = None,
        on_change: "Callable[[], None] | None" = None,
    ) -> None:
        self.settings = settings
        self.catalog = catalog
        self.validator = validator or ValidationPipeline()
        self.clock = clock or SystemClock()
        # Optional observer fired after any state change (e.g. Project Context
        # refresh). Decoupled: default None so the registry has no dependency on
        # the context subsystem.
        self.on_change: "Callable[[], None] | None" = on_change

    @classmethod
    def from_settings(cls, settings: Settings, clock: Clock | None = None) -> "ResourceRegistry":
        catalog = KnowledgeCatalog.from_settings(settings, clock=clock)
        catalog.initialize()
        return cls(settings, catalog, clock=clock)

    def _notify_change(self) -> None:
        if self.on_change is None:
            return
        try:
            self.on_change()
        except Exception as exc:  # observer failure must never break registration
            log.warning("on_change hook failed: %s", exc)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #
    def build_metadata(
        self,
        file_path: str | Path,
        *,
        track: str,
        course: str,
        module: str,
        title: str,
        doc_type: str | DocType = DocType.OTHER,
        role: str | Role = Role.MATERIAL,
        language: str | Language = Language.EN,
        slug: str | None = None,
        subject: str | None = None,
        week: int | None = None,
        lecture: str | None = None,
        topics: list[str] | None = None,
        subtopics: list[str] | None = None,
        parent_resource_id: str | None = None,
        parallel_group: str | None = None,
        is_translation: bool = False,
        title_i18n: dict[str, str] | None = None,
        source: dict | None = None,
        pedagogy: dict | None = None,
        persistence: str | Persistence = Persistence.PERMANENT,
        update: bool = False,
        strict: bool = True,
    ) -> ResourceMetadata:
        """Build and validate a ResourceMetadata **without persisting it**.

        Factored out of ``register`` so the ingestion pipeline can obtain a
        metadata seed early, enrich it through stages, then persist via
        ``commit``. ``register`` is now ``build_metadata`` + ``commit``.
        """
        abs_path = self._resolve(file_path)
        if not abs_path.is_file():
            raise RegistryError(f"Cannot register — file not found: {abs_path}")

        doc_type = DocType(str(doc_type))
        role = Role(str(role))
        language = Language(str(language))
        persistence = Persistence(str(persistence))

        resource_id = ids.make_resource_id(track, course, module, slug or title)
        file_info = self._build_file_info(abs_path)

        # Duplicate-content advisory (same bytes already registered elsewhere).
        for dup in self.catalog.find_by_sha256(file_info.sha256):
            if dup["resource_id"] != resource_id:
                log.warning(
                    "Content hash of %s already registered as %s (possible duplicate).",
                    resource_id,
                    dup["resource_id"],
                )

        existing = self.catalog.get(resource_id)
        if existing is not None and not update:
            raise DuplicateResourceError(
                f"resource_id already registered: {resource_id} (pass update=True to re-version)."
            )

        version = existing.lifecycle.version + 1 if existing is not None else 1
        created_at = existing.created_at if existing is not None else self.clock.now_iso()

        meta = ResourceMetadata(
            resource_id=resource_id,
            parent_resource_id=parent_resource_id,
            title=title,
            title_i18n=title_i18n or {},
            slug=slug or ids.slugify(title),
            track=track,
            course=course,
            subject=subject,
            module=module,
            week=week,
            lecture=lecture,
            topics=topics or [],
            subtopics=subtopics or [],
            doc_type=doc_type,
            role=role,
            language=language,
            is_translation=is_translation,
            parallel_group=parallel_group,
            file=file_info,
            source=SourceInfo(**source) if source else SourceInfo(
                origin="unknown", original_filename=abs_path.name
            ),
            pedagogy=PedagogyInfo(**pedagogy) if pedagogy else PedagogyInfo(),
            created_at=created_at,
        )
        meta.provenance.pipeline_version = self.settings.metadata.pipeline_version
        meta.retrieval.chunk_strategy = _CHUNK_BY_DOCTYPE.get(doc_type, ChunkStrategy.NONE)
        meta.lifecycle.version = version
        meta.lifecycle.persistence = persistence

        result = self.validator.run(meta, self._validation_ctx())
        meta.status.validation_status = result.status
        if not result.ok and strict:
            raise ValidationError(
                f"{resource_id} failed validation: "
                + "; ".join(i.message for i in result.errors),
                errors=[i.message for i in result.errors],
            )
        return meta

    def commit(self, meta: ResourceMetadata, *, write_sidecar_file: bool = True) -> ResourceMetadata:
        """Persist a (possibly pipeline-enriched) metadata: sidecar + catalog + event.

        This is the "Registry Update -> Knowledge Catalog Update" step of the
        ingestion pipeline.
        """
        abs_path = self._resolve(meta.file.file_path)
        existing = self.catalog.get(meta.resource_id)
        content_changed = existing is not None and existing.file.sha256 != meta.file.sha256

        if write_sidecar_file and abs_path.is_file():
            write_sidecar(
                meta, abs_path,
                suffix=self.settings.sidecar.suffix, fmt=self.settings.sidecar.format,
            )

        self.catalog.upsert_resource(meta)
        self.catalog.record_event(
            meta.resource_id,
            "updated" if existing is not None else "registered",
            from_hash=existing.file.sha256 if existing else None,
            to_hash=meta.file.sha256,
            version=meta.lifecycle.version,
            details={"content_changed": content_changed} if existing else None,
        )
        if content_changed:
            self.set_status(meta.resource_id, processing_status=ProcessingStatus.PENDING)
            self.catalog.record_event(
                meta.resource_id, "content_changed",
                from_hash=existing.file.sha256, to_hash=meta.file.sha256,
                version=meta.lifecycle.version,
            )
        log.info("Committed %s (v%d, %s).", meta.resource_id, meta.lifecycle.version, meta.doc_type)
        self._notify_change()
        return meta

    def register(
        self,
        file_path: str | Path,
        *,
        track: str,
        course: str,
        module: str,
        title: str,
        doc_type: str | DocType = DocType.OTHER,
        role: str | Role = Role.MATERIAL,
        language: str | Language = Language.EN,
        slug: str | None = None,
        subject: str | None = None,
        week: int | None = None,
        lecture: str | None = None,
        topics: list[str] | None = None,
        subtopics: list[str] | None = None,
        parent_resource_id: str | None = None,
        parallel_group: str | None = None,
        is_translation: bool = False,
        title_i18n: dict[str, str] | None = None,
        source: dict | None = None,
        pedagogy: dict | None = None,
        persistence: str | Persistence = Persistence.PERMANENT,
        update: bool = False,
        write_sidecar_file: bool = True,
        strict: bool = True,
    ) -> ResourceMetadata:
        """Register (or, with ``update=True``, re-version) a resource = build + commit."""
        meta = self.build_metadata(
            file_path, track=track, course=course, module=module, title=title,
            doc_type=doc_type, role=role, language=language, slug=slug, subject=subject,
            week=week, lecture=lecture, topics=topics, subtopics=subtopics,
            parent_resource_id=parent_resource_id, parallel_group=parallel_group,
            is_translation=is_translation, title_i18n=title_i18n, source=source,
            pedagogy=pedagogy, persistence=persistence, update=update, strict=strict,
        )
        return self.commit(meta, write_sidecar_file=write_sidecar_file)

    # ------------------------------------------------------------------ #
    # Status transitions (used by the ingestion pipeline in later phases)
    # ------------------------------------------------------------------ #
    def set_status(
        self,
        resource_id: str,
        *,
        processing_status: str | ProcessingStatus | None = None,
        ocr_status: str | StageStatus | None = None,
        embedding_status: str | StageStatus | None = None,
        graph_status: str | StageStatus | None = None,
        vector_status: str | StageStatus | None = None,
        chunk_count: int | None = None,
        embedder_version: str | None = None,
        mark_indexed_now: bool = False,
    ) -> ResourceMetadata:
        meta = self.catalog.get(resource_id)
        if meta is None:
            raise RegistryError(f"Unknown resource_id: {resource_id}")

        if processing_status is not None:
            meta.status.processing_status = ProcessingStatus(str(processing_status))
        if ocr_status is not None:
            meta.status.ocr_status = StageStatus(str(ocr_status))
        if embedding_status is not None:
            meta.status.embedding_status = StageStatus(str(embedding_status))
        if graph_status is not None:
            meta.status.graph_status = StageStatus(str(graph_status))
        if vector_status is not None:
            meta.status.vector_status = StageStatus(str(vector_status))
        if chunk_count is not None:
            meta.retrieval.chunk_count = chunk_count
        if embedder_version is not None:
            meta.lifecycle.embedder_version = embedder_version
        if mark_indexed_now:
            meta.last_indexed_at = self.clock.now_iso()

        meta.touch()
        self.catalog.upsert_resource(meta)
        self.catalog.record_event(resource_id, "status_changed",
                                  version=meta.lifecycle.version)
        self._notify_change()
        return meta

    def get(self, resource_id: str) -> ResourceMetadata | None:
        return self.catalog.get(resource_id)

    def close(self) -> None:
        self.catalog.close()

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _resolve(self, file_path: str | Path) -> Path:
        p = Path(file_path)
        return p.resolve() if p.is_absolute() else (self.settings.project_root / p).resolve()

    def _rel_to_root(self, abs_path: Path) -> str:
        try:
            return abs_path.relative_to(self.settings.project_root).as_posix()
        except ValueError:
            # File lives outside the project root (e.g. a temp fixture) — store absolute.
            return abs_path.as_posix()

    def _build_file_info(self, abs_path: Path) -> FileInfo:
        st = abs_path.stat()
        return FileInfo(
            file_name=abs_path.name,
            file_path=self._rel_to_root(abs_path),
            file_size=st.st_size,
            sha256=sha256_file(abs_path, self.settings.change_detection.hash_chunk_bytes),
            mime_type=mimetypes.guess_type(abs_path.name)[0],
            created_date=_iso(st.st_ctime),
            last_modified=_iso(st.st_mtime),
        )

    def _validation_ctx(self) -> ValidationContext:
        return ValidationContext(
            project_root=self.settings.project_root,
            supported_languages=set(self.settings.metadata.supported_languages),
            valid_tracks=self.settings.valid_track_ids(),
            valid_courses=self.settings.valid_course_ids(),
            check_files=True,
            verify_hash=False,  # we just computed it during registration
        )


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).replace(microsecond=0).isoformat()
