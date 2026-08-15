"""ResourceMetadata — the single, authoritative description of one resource.

Design goals (Task 2): one record must carry enough information to serve Hybrid
RAG, Parent-Child retrieval, Graph RAG, RL, future Web/Video, incremental
indexing, provenance, and citation generation — WITHOUT any of those subsystems
existing yet. We do that by reserving typed, defaulted fields for each concern
now, so later phases fill them in rather than migrate the schema.

The model is grouped into sub-objects so the JSON sidecar stays readable and each
concern is locatable:

    identity/classification   (top level)
    file:        FileInfo         -> file_name, path, size, sha256, dates
    source:      SourceInfo       -> provenance of the ORIGINAL (origin/url/author/license)
    provenance:  ProvenanceInfo   -> how text was obtained + content_hash + pipeline
    pedagogy:    PedagogyInfo      -> tags/keywords/objectives/prereqs/difficulty
    status:      StatusInfo        -> processing/ocr/embedding/graph/vector/validation
    lifecycle:   LifecycleInfo     -> persistence/record_status/version/supersedes
    retrieval:   RetrievalInfo     -> chunk strategy/counts/ids, graph & video/web links

Every enum serialises to its string value, so a sidecar is plain, diffable JSON.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ala.core import ids
from ala.core.clock import utcnow_iso
from ala.core.enums import (
    AsrSource,
    ChunkStrategy,
    Difficulty,
    DocType,
    ExtractionMethod,
    Language,
    Persistence,
    ProcessingStatus,
    RecordStatus,
    RelationSource,
    RelationType,
    Role,
    SourceTier,
    StageStatus,
    ValidationStatus,
)

# 2.0.0: Milestone 1.5 — academic block, difficulty_score, typed relationships,
# nested video/web sub-models, and processing-history provenance.
SCHEMA_VERSION = "2.0.0"

_Strict = ConfigDict(extra="forbid", use_enum_values=True, validate_assignment=True)


# --------------------------------------------------------------------------- #
# Sub-models
# --------------------------------------------------------------------------- #
class FileInfo(BaseModel):
    """Physical facts about the raw file on disk."""

    model_config = _Strict

    file_name: str
    file_path: str                      # project-root-relative
    file_size: int = 0                  # bytes
    sha256: str = ""                    # hex digest of raw bytes (change detection)
    mime_type: str | None = None
    created_date: str | None = None     # filesystem ctime, ISO-8601
    last_modified: str | None = None    # filesystem mtime, ISO-8601


class SourceInfo(BaseModel):
    """Where the ORIGINAL came from — provenance & rights tracking."""

    model_config = _Strict

    origin: str = "unknown"             # e.g. digilians-lms | youtube | textbook | web
    original_filename: str | None = None
    url: str | None = None
    author: str | None = None
    publisher: str | None = None
    captured_at: str | None = None
    captured_by: str | None = None
    license: str = "personal-study; no redistribution"


class ProcessingStep(BaseModel):
    """One entry in a resource's processing lineage (M1.5).

    Appended every time a pipeline stage runs (extract/ocr/chunk/embed/graph),
    giving an auditable, reproducible history rather than just a current status.
    """

    model_config = _Strict

    step: str                              # e.g. "extract" | "ocr" | "embed"
    status: StageStatus = StageStatus.DONE
    tool: str | None = None                # e.g. "pypdf" | "faster-whisper"
    version: str | None = None             # tool/model version
    duration_ms: int | None = None
    started_at: str | None = None
    timestamp: str = Field(default_factory=utcnow_iso)   # when recorded
    notes: str | None = None


class ProvenanceInfo(BaseModel):
    """How machine-readable content was (or will be) derived, + integrity + lineage."""

    model_config = _Strict

    extraction_method: ExtractionMethod = ExtractionMethod.NONE
    extraction_confidence: float | None = None   # 0..1, filled by the extractor
    pipeline_version: str = "0.1.0"
    content_hash: str = ""                        # hash of extracted text (set later)
    ingested_at: str = Field(default_factory=utcnow_iso)
    history: list[ProcessingStep] = Field(default_factory=list)   # processing lineage


class AcademicInfo(BaseModel):
    """Resource-level academic metadata (M1.5).

    NOTE (design decision): course-level facts (program, prerequisite_courses,
    the canonical course_code) live in the taxonomy so they aren't duplicated on
    every resource. The fields here are the ones that genuinely vary per
    resource; course_code is kept as a convenient denormalized label for
    citations and can be left null to defer to the taxonomy.
    """

    model_config = _Strict

    course_code: str | None = None          # e.g. "DS201" (citation convenience)
    instructor: str | None = None
    semester: str | None = None             # e.g. "2026-Spring"
    estimated_study_time_min: int | None = None
    lab_required: bool = False
    exam_weight: float | None = None        # 0..1; meaningful mainly for assessments


class PedagogyInfo(BaseModel):
    """Learning-facing metadata (also feeds RL difficulty & prerequisite logic)."""

    model_config = _Strict

    tags: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    learning_objectives: list[str] = Field(default_factory=list)  # (== "learning_outcomes")
    prerequisites: list[str] = Field(default_factory=list)   # concept_ids or resource_ids
    difficulty: Difficulty = Difficulty.UNKNOWN              # human-facing band
    difficulty_score: float | None = None                   # 0..1, numeric, for RL


class StatusInfo(BaseModel):
    """Per-stage processing state — the map of what still needs doing."""

    model_config = _Strict

    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    ocr_status: StageStatus = StageStatus.NOT_REQUIRED
    embedding_status: StageStatus = StageStatus.PENDING
    graph_status: StageStatus = StageStatus.PENDING
    vector_status: StageStatus = StageStatus.PENDING
    validation_status: ValidationStatus = ValidationStatus.UNVALIDATED


class LifecycleInfo(BaseModel):
    """Versioning & record state (supersede-not-delete)."""

    model_config = _Strict

    persistence: Persistence = Persistence.PERMANENT
    record_status: RecordStatus = RecordStatus.ACTIVE
    version: int = 1
    supersedes: str | None = None       # resource_id of the version this replaces
    superseded_by: str | None = None
    embedder_version: str | None = None  # stamped when embedded (V3 requirement)


class RetrievalInfo(BaseModel):
    """Everything the retrieval/graph/video/web subsystems will populate.

    Present now (empty) so incremental indexing can fill them without a schema
    migration. This is what makes the record "future-proof" per the brief.
    """

    model_config = _Strict

    chunk_strategy: ChunkStrategy = ChunkStrategy.NONE
    chunk_count: int = 0
    parent_chunk_ids: list[str] = Field(default_factory=list)
    child_chunk_ids: list[str] = Field(default_factory=list)
    graph_entity_ids: list[str] = Field(default_factory=list)   # concept/entity ids
    concepts: list[str] = Field(default_factory=list)           # concept_ids (Graph RAG)
    video_ids: list[str] = Field(default_factory=list)          # future Video module
    web_source_ids: list[str] = Field(default_factory=list)     # future Web fallback
    anchors: dict = Field(default_factory=dict)                 # video/web citation anchors


class ResourceRelationship(BaseModel):
    """One typed edge to another resource (M1.5).

    Replaces six parallel link arrays (related/depends_on/extends/recommended_*/
    similar) with a single, uniform, extensible edge — mirroring the Concept
    Graph edge model. ``source`` distinguishes curated from computed links so the
    latter can be recomputed without hand-editing.
    """

    model_config = _Strict

    type: RelationType
    target_resource_id: str
    source: RelationSource = RelationSource.MANUAL
    confidence: float | None = None
    note: str | None = None


class VideoInfo(BaseModel):
    """Video-specific metadata (present only when doc_type == video)."""

    model_config = _Strict

    video_id: str | None = None
    channel: str | None = None
    playlist: str | None = None
    duration_sec: float | None = None
    transcript_language: Language | None = None
    transcript_version: str | None = None
    asr_source: AsrSource | None = None     # human_captions | auto_captions | whisper


class WebInfo(BaseModel):
    """Web-specific metadata (present only when doc_type == web).

    NOTE: ``url`` and ``license`` are intentionally NOT here — they live in
    ``source.url`` / ``source.license`` and are reused, not duplicated.
    """

    model_config = _Strict

    domain: str | None = None
    crawl_date: str | None = None
    last_verified: str | None = None
    source_tier: SourceTier = SourceTier.UNKNOWN


# --------------------------------------------------------------------------- #
# Root model
# --------------------------------------------------------------------------- #
class ResourceMetadata(BaseModel):
    """One resource, fully described. Self-validating on construction."""

    model_config = _Strict

    # -- schema/versioning of the record itself --
    schema_version: str = SCHEMA_VERSION

    # -- identity & classification --
    resource_id: str
    parent_resource_id: str | None = None
    title: str
    title_i18n: dict[str, str] = Field(default_factory=dict)   # {"en": "...", "ar": "..."}
    slug: str = ""

    track: str
    course: str
    subject: str | None = None          # optional finer subject label
    module: str | None = None
    week: int | None = None
    lecture: str | None = None
    topics: list[str] = Field(default_factory=list)
    subtopics: list[str] = Field(default_factory=list)

    doc_type: DocType = DocType.OTHER   # "Resource Type"
    role: Role = Role.MATERIAL
    language: Language = Language.EN
    is_translation: bool = False
    parallel_group: str | None = None   # links en/ar renderings of one lesson

    # -- grouped detail --
    file: FileInfo
    source: SourceInfo = Field(default_factory=SourceInfo)
    provenance: ProvenanceInfo = Field(default_factory=ProvenanceInfo)
    pedagogy: PedagogyInfo = Field(default_factory=PedagogyInfo)
    academic: AcademicInfo = Field(default_factory=AcademicInfo)      # M1.5
    status: StatusInfo = Field(default_factory=StatusInfo)
    lifecycle: LifecycleInfo = Field(default_factory=LifecycleInfo)
    retrieval: RetrievalInfo = Field(default_factory=RetrievalInfo)

    # -- typed relationships (single edge list; M1.5) --
    relationships: list[ResourceRelationship] = Field(default_factory=list)

    # -- optional, doc-type-specific blocks (null unless relevant; M1.5) --
    video: VideoInfo | None = None
    web: WebInfo | None = None

    # -- record timestamps --
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    last_indexed_at: str | None = None

    # -- validators --
    @field_validator("resource_id")
    @classmethod
    def _valid_id(cls, v: str) -> str:
        if not ids.is_valid_resource_id(v):
            raise ValueError(
                f"resource_id '{v}' is not canonical "
                "(<track>.<course>.<module>.<slug>, lowercase a-z0-9-)."
            )
        return v

    # -- convenience --
    def touch(self) -> None:
        """Update ``updated_at`` to now (call after any mutation)."""
        self.updated_at = utcnow_iso()

    def add_processing_step(
        self,
        step: str,
        *,
        status: StageStatus = StageStatus.DONE,
        tool: str | None = None,
        version: str | None = None,
        duration_ms: int | None = None,
        started_at: str | None = None,
        notes: str | None = None,
    ) -> ProcessingStep:
        """Append a stage to the processing lineage and return it (M1.5)."""
        entry = ProcessingStep(
            step=step, status=status, tool=tool, version=version,
            duration_ms=duration_ms, started_at=started_at, notes=notes,
        )
        self.provenance.history.append(entry)
        self.touch()
        return entry

    def add_relationship(
        self,
        rel_type: RelationType,
        target_resource_id: str,
        *,
        source: RelationSource = RelationSource.MANUAL,
        confidence: float | None = None,
    ) -> None:
        """Add a typed edge to another resource, de-duplicating (type, target)."""
        for r in self.relationships:
            if r.type == rel_type and r.target_resource_id == target_resource_id:
                return
        self.relationships.append(
            ResourceRelationship(
                type=rel_type, target_resource_id=target_resource_id,
                source=source, confidence=confidence,
            )
        )
        self.touch()

    def to_json(self, *, indent: int = 2) -> str:
        """Serialise to a diffable JSON string (enums as their values)."""
        return self.model_dump_json(indent=indent)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict) -> "ResourceMetadata":
        return cls.model_validate(data)

    def to_catalog_row(self) -> dict:
        """Flatten the columns the SQLite catalog promotes for fast query.

        The full object is *also* stored as JSON in the catalog, so nothing here
        is lossy — these are just the indexed/filterable projections.
        """
        return {
            "resource_id": self.resource_id,
            "parent_resource_id": self.parent_resource_id,
            "title": self.title,
            "track": self.track,
            "course": self.course,
            "subject": self.subject,
            "module": self.module,
            "week": self.week,
            "lecture": self.lecture,
            "doc_type": str(self.doc_type),
            "role": str(self.role),
            "language": str(self.language),
            "record_status": str(self.lifecycle.record_status),
            "version": self.lifecycle.version,
            "persistence": str(self.lifecycle.persistence),
            "parallel_group": self.parallel_group,
            "file_path": self.file.file_path,
            "file_name": self.file.file_name,
            "file_size": self.file.file_size,
            "sha256": self.file.sha256,
            "content_hash": self.provenance.content_hash,
            "processing_status": str(self.status.processing_status),
            "ocr_status": str(self.status.ocr_status),
            "embedding_status": str(self.status.embedding_status),
            "graph_status": str(self.status.graph_status),
            "vector_status": str(self.status.vector_status),
            "validation_status": str(self.status.validation_status),
            "chunk_count": self.retrieval.chunk_count,
            "difficulty": str(self.pedagogy.difficulty),
            "difficulty_score": self.pedagogy.difficulty_score,
            "course_code": self.academic.course_code,
            "instructor": self.academic.instructor,
            "lab_required": int(self.academic.lab_required),
            "has_video": int(self.video is not None),
            "has_web": int(self.web is not None),
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_indexed_at": self.last_indexed_at,
            "created_date": self.file.created_date,
            "last_modified": self.file.last_modified,
        }
