"""Stage 1 — Resource Discovery.

Finds ingestible files and infers their classification from the managed folder
layout ``raw/<track>/<course>/<module>/<slug>/source.<ext>``. Sidecars and
derived artifacts are skipped. For files outside the managed layout, the caller
supplies an explicit classification via ``ingest_path``.
"""

from __future__ import annotations

from pathlib import Path

from ala.config.settings import Settings
from ala.core import ids
from ala.core.enums import DocType, Role
from ala.ingestion.context import IngestionJob, ResourceClassification

_DOCTYPE_BY_EXT = {
    ".pdf": DocType.LESSON_PAGE,
    ".pptx": DocType.LECTURE_SLIDES,
    ".ppsx": DocType.LECTURE_SLIDES,
    ".docx": DocType.LESSON_PAGE,
    ".txt": DocType.OTHER,
    ".md": DocType.LESSON_PAGE,
    ".markdown": DocType.LESSON_PAGE,
    ".html": DocType.WEB,
    ".htm": DocType.WEB,
    ".ipynb": DocType.NOTEBOOK,
}
_ROLE_BY_DOCTYPE = {
    DocType.NOTEBOOK: Role.CODE,
}


class ResourceDiscovery:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def discover(self, root: str | Path | None = None) -> list[IngestionJob]:
        base = self.settings.abspath(str(root)) if root else self.settings.raw_path
        base = Path(base)
        jobs: list[IngestionJob] = []
        if not base.exists():
            return jobs
        # Ensure resource_id uniqueness: two files whose stems slugify identically
        # in the same module (e.g. a chapter's .ppsx and its .pdf export) would
        # otherwise collide. Disambiguate the slug deterministically, mirroring the
        # importer's path de-duplication.
        seen: set[tuple[str, str, str, str]] = set()
        for f in sorted(base.rglob("*")):
            if f.is_file() and ".meta." not in f.name and f.suffix.lower() in _DOCTYPE_BY_EXT:
                cls = self._infer(f, base)
                key = (cls.track, cls.course, cls.module, cls.slug)
                if key in seen:
                    n = 2
                    while (cls.track, cls.course, cls.module, f"{cls.slug}-{n}") in seen:
                        n += 1
                    cls.slug = f"{cls.slug}-{n}"
                    key = (cls.track, cls.course, cls.module, cls.slug)
                seen.add(key)
                jobs.append(IngestionJob(f, cls))
        return jobs

    def discover_file(
        self, path: str | Path, classification: ResourceClassification
    ) -> IngestionJob:
        return IngestionJob(Path(path), classification)

    def _infer(self, path: Path, base: Path) -> ResourceClassification:
        parts = path.relative_to(base).parts
        track = parts[0] if len(parts) >= 1 else "technical"
        course = parts[1] if len(parts) >= 2 else "misc"
        module = parts[2] if len(parts) >= 3 else "m00"
        doc_type = _DOCTYPE_BY_EXT.get(path.suffix.lower(), DocType.OTHER)
        return ResourceClassification(
            track=track,
            course=course,
            module=module,
            title=path.stem,
            slug=ids.slugify(path.stem),
            doc_type=doc_type,
            role=_ROLE_BY_DOCTYPE.get(doc_type, Role.MATERIAL),
        )
