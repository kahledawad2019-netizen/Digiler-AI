"""Change detection & incremental-indexing support (Task 1 & Task 4).

Answers the question "which resources need (re)processing?" with certainty by
comparing the SHA-256 recorded in the catalog against the bytes on disk:

    NEW       file under the KB root that the catalog has never seen
    UNCHANGED catalog hash == disk hash
    MODIFIED  catalog hash != disk hash (edited/replaced -> must reprocess)
    MISSING   catalog has it, disk no longer does (deleted/moved)

``to_reprocess()`` folds in resources whose pipeline status is PENDING/FAILED,
so a fresh registration or a previously-failed stage is also picked up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ala.catalog.repository import KnowledgeCatalog
from ala.core.enums import ProcessingStatus
from ala.core.hashing import sha256_file

_SIDECAR_MARKER = ".meta."


class ChangeType(str, Enum):
    NEW = "new"
    UNCHANGED = "unchanged"
    MODIFIED = "modified"
    MISSING = "missing"


@dataclass
class ChangeReport:
    new: list[Path] = field(default_factory=list)          # unregistered files
    modified: list[str] = field(default_factory=list)      # resource_ids
    unchanged: list[str] = field(default_factory=list)      # resource_ids
    missing: list[str] = field(default_factory=list)        # resource_ids
    needs_status_reprocess: list[str] = field(default_factory=list)  # PENDING/FAILED

    def to_reprocess(self) -> list[str]:
        """resource_ids that should be pushed through the ingestion pipeline."""
        seen: list[str] = []
        for rid in [*self.modified, *self.needs_status_reprocess]:
            if rid not in seen:
                seen.append(rid)
        return seen

    def summary(self) -> dict[str, int]:
        return {
            "new": len(self.new),
            "modified": len(self.modified),
            "unchanged": len(self.unchanged),
            "missing": len(self.missing),
            "needs_status_reprocess": len(self.needs_status_reprocess),
        }


class ChangeDetector:
    def __init__(self, catalog: KnowledgeCatalog, project_root: Path) -> None:
        self.catalog = catalog
        self.project_root = Path(project_root)

    # -- single resource -------------------------------------------------- #
    def classify(self, resource_id: str) -> ChangeType:
        row = self.catalog.get_row(resource_id)
        if row is None:
            raise KeyError(f"resource_id not in catalog: {resource_id}")
        path = (self.project_root / row["file_path"]).resolve()
        if not path.is_file():
            return ChangeType.MISSING
        return (
            ChangeType.UNCHANGED
            if sha256_file(path) == row["sha256"]
            else ChangeType.MODIFIED
        )

    def needs_reprocessing(self, resource_id: str) -> bool:
        row = self.catalog.get_row(resource_id)
        if row is None:
            return False
        if row["processing_status"] in {ProcessingStatus.PENDING.value, ProcessingStatus.FAILED.value}:
            return True
        return self.classify(resource_id) == ChangeType.MODIFIED

    # -- whole tree ------------------------------------------------------- #
    def scan(self, root: str | Path | None = None) -> ChangeReport:
        """Compare the catalog against the filesystem and report differences."""
        report = ChangeReport()
        known_paths: set[str] = set()

        for row in self.catalog.list_all(record_status="active"):
            rid = row["resource_id"]
            known_paths.add(_norm(row["file_path"]))
            path = (self.project_root / row["file_path"]).resolve()
            if not path.is_file():
                report.missing.append(rid)
            elif sha256_file(path) == row["sha256"]:
                report.unchanged.append(rid)
            else:
                report.modified.append(rid)
            if row["processing_status"] in {
                ProcessingStatus.PENDING.value,
                ProcessingStatus.FAILED.value,
            }:
                report.needs_status_reprocess.append(rid)

        # NEW: files under root not matching any known file_path.
        if root is not None:
            root_path = Path(root)
            if not root_path.is_absolute():
                root_path = self.project_root / root_path
            for f in _iter_content_files(root_path):
                rel = _norm(str(f.relative_to(self.project_root)))
                if rel not in known_paths:
                    report.new.append(f)

        return report


def _iter_content_files(root: Path):
    if not root.exists():
        return
    for f in root.rglob("*"):
        if f.is_file() and _SIDECAR_MARKER not in f.name:
            yield f


def _norm(path_str: str) -> str:
    return path_str.replace("\\", "/")
