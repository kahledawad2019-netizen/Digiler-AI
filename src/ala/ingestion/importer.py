"""CorpusImporter — organize an external corpus into the managed Knowledge Base.

Copies (never moves/modifies) the original files from an arbitrary drop folder
(e.g. ``Basic_knowladg/``) into the managed layout
``knowledge_base/raw/<track>/<course>/<module>/<file>`` that the ingestion
pipeline's discovery understands — inferring track/course/module from the source
folder structure and applying disposition rules:

    COPY          prose resource -> ingested by the pipeline
    COPY_DATASET  spreadsheet/csv/sql -> copied + registered as role=dataset (not chunked)
    QUARANTINE    credentials/secrets -> copied to _quarantine, never ingested
    SKIP          junk / archives / saved-web dumps / shadow copies

Originals are read-only; this is a copy-in importer, matching the platform rule
"raw is immutable; nothing enters the KB without metadata & provenance".
"""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ala.config.settings import Settings
from ala.core import ids
from ala.core.enums import DocType, Role
from ala.registry.registry import ResourceRegistry

log = logging.getLogger("ala.ingestion.importer")

# course-folder substring -> (track, course_id) in the taxonomy
_COURSE_MAP: list[tuple[str, tuple[str, str]]] = [
    ("agentic ai", ("technical", "agentic-ai")),
    ("applied deep learning", ("technical", "applied-dl")),
    ("applied statistics", ("technical", "applied-stats")),
    ("excel", ("technical", "excel-ai")),
    ("data_minig", ("technical", "dmv")),
    ("data mining", ("technical", "dmv")),
    ("introduction to ai", ("technical", "aiml")),
    ("english", ("nontechnical", "eng")),
]

_PROSE_EXTS = {".pdf", ".pptx", ".ppsx", ".docx", ".txt", ".md", ".markdown", ".html", ".htm", ".ipynb"}
_DATASET_EXTS = {".xlsx", ".xls", ".csv", ".sql"}
_SKIP_EXTS = {".zip", ".mhtml", ".crdownload"}

_WRAPPER_RE = re.compile(r"-\d{8}T\d{6}Z-\d+-\d+$")   # Google-Takeout wrapper folder
_WEEK_RE = re.compile(r"week\s*0*(\d+)", re.IGNORECASE)
_SESSION_RE = re.compile(r"session\s*0*(\d+)", re.IGNORECASE)


class Disposition(str, Enum):
    COPY = "copy"
    COPY_DATASET = "copy_dataset"
    QUARANTINE = "quarantine"
    SKIP = "skip"


@dataclass
class ImportItem:
    source: Path
    disposition: Disposition
    reason: str = ""
    track: str | None = None
    course: str | None = None
    module: str | None = None
    dest_rel: str | None = None      # project-root-relative destination


@dataclass
class ImportPlan:
    items: list[ImportItem] = field(default_factory=list)

    def by_disposition(self, d: Disposition) -> list[ImportItem]:
        return [i for i in self.items if i.disposition is d]

    def summary(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for i in self.items:
            out[i.disposition.value] = out.get(i.disposition.value, 0) + 1
        return out


@dataclass
class ImportReport:
    copied: int = 0
    datasets_registered: int = 0
    quarantined: int = 0
    skipped: int = 0
    by_course: dict[str, int] = field(default_factory=dict)


class CorpusImporter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.raw_root = settings.raw_path
        self.quarantine_root = settings.abspath(settings.paths.quarantine_dir)

    # ------------------------------------------------------------------ #
    def plan(self, source_root: str | Path) -> ImportPlan:
        root = Path(source_root)
        if not root.is_absolute():
            root = (self.settings.project_root / root)
        root = root.resolve()
        plan = ImportPlan()
        used_dests: set[str] = set()

        for f in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = f.relative_to(root)
            item = self._classify(f, rel, used_dests)
            plan.items.append(item)
        return plan

    def execute(self, plan: ImportPlan, registry: ResourceRegistry | None = None) -> ImportReport:
        report = ImportReport()
        for item in plan.items:
            if item.disposition is Disposition.SKIP:
                report.skipped += 1
                continue
            if item.disposition is Disposition.QUARANTINE:
                self.quarantine_root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item.source, self.quarantine_root / item.source.name)
                report.quarantined += 1
                continue

            dest = self.settings.project_root / item.dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists() or dest.stat().st_size != item.source.stat().st_size:
                shutil.copy2(item.source, dest)
            report.copied += 1
            report.by_course[item.course] = report.by_course.get(item.course, 0) + 1

            if item.disposition is Disposition.COPY_DATASET and registry is not None:
                self._register_dataset(item, dest, registry)
                report.datasets_registered += 1
        return report

    # ------------------------------------------------------------------ #
    def _classify(self, source: Path, rel: Path, used: set[str]) -> ImportItem:
        name = source.name
        ext = source.suffix.lower()

        # disposition first (security + junk win over everything)
        if name.endswith(".ipynb.txt"):
            return ImportItem(source, Disposition.SKIP, reason="notebook shadow copy")
        if ext == ".json" and "client_secret" in name.lower():
            return ImportItem(source, Disposition.QUARANTINE, reason="credential file (do not ingest)")
        if ext in _SKIP_EXTS:
            return ImportItem(source, Disposition.SKIP, reason=f"skipped type {ext}")
        if ext == ".json":
            return ImportItem(source, Disposition.SKIP, reason="non-content json")

        track, course, module = self._locate(rel)
        stem = ids.slugify(source.stem) or "resource"
        dest_rel = self._unique_dest(track, course, module, stem, ext, used)

        if ext in _DATASET_EXTS:
            return ImportItem(source, Disposition.COPY_DATASET, "dataset", track, course, module, dest_rel)
        if ext in _PROSE_EXTS:
            return ImportItem(source, Disposition.COPY, "prose", track, course, module, dest_rel)
        return ImportItem(source, Disposition.SKIP, reason=f"unsupported type {ext}")

    def _locate(self, rel: Path) -> tuple[str, str, str]:
        parts = list(rel.parts)
        if parts and _WRAPPER_RE.search(parts[0]):
            parts = parts[1:]                     # drop Google-Takeout wrapper
        course_folder = parts[0] if parts else "misc"
        module_dirs = parts[1:-1]                 # between course and filename

        track, course = self._course_of(course_folder)
        module = self._module_slug(module_dirs)
        return track, course, module

    @staticmethod
    def _course_of(course_folder: str) -> tuple[str, str]:
        low = course_folder.lower()
        for needle, (track, course) in _COURSE_MAP:
            if needle in low:
                return track, course
        return "technical", (ids.slugify(course_folder)[:24] or "misc")

    @staticmethod
    def _module_slug(dirs: tuple[str, ...] | list[str]) -> str:
        joined = " / ".join(dirs)
        wk = _WEEK_RE.search(joined)
        ss = _SESSION_RE.search(joined)
        if wk and ss:
            return f"w{int(wk.group(1)):02d}-s{int(ss.group(1))}"
        if wk:
            return f"w{int(wk.group(1)):02d}"
        if dirs:
            return (ids.slugify("-".join(dirs))[:24] or "general")
        return "general"

    def _unique_dest(self, track, course, module, stem, ext, used: set[str]) -> str:
        base = f"{self.settings.paths.raw_dir}/{track}/{course}/{module}/{stem}"
        candidate = f"{base}{ext}"
        n = 2
        while candidate in used:
            candidate = f"{base}-{n}{ext}"
            n += 1
        used.add(candidate)
        return candidate

    def _register_dataset(self, item: ImportItem, dest: Path, registry: ResourceRegistry) -> None:
        registry.register(
            dest, track=item.track, course=item.course, module=item.module,
            title=dest.stem, doc_type=DocType.DATASET, role=Role.DATASET,
            update=True, strict=False,
        )
