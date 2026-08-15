"""Pipeline outputs: the ResourcePackage and the IngestionResult.

The **ResourcePackage** is the Stage-10 deliverable required by the milestone:
original file reference + structured content + clean text + metadata + academic
structure + processing history + validation results (+ language w/ confidence).
It is persisted under ``knowledge_base/derived/<resource_id>/package.json``.

Deliberately contains NO embeddings, chunks, vectors, or graph — this milestone
only produces high-quality structured data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ala.fabric.learning_resource import LearningResource
from ala.ingestion.errors import StageOutcome


class IngestionStatus(str, Enum):
    SUCCESS = "success"     # all stages ok
    PARTIAL = "partial"     # a non-critical stage failed; usable output produced
    FAILED = "failed"       # a critical stage failed; no usable output
    SKIPPED = "skipped"     # nothing to do (e.g. unchanged & already processed)


@dataclass
class ResourcePackage:
    """Everything known about a processed resource, ready to persist."""

    resource_id: str
    resource: LearningResource
    clean_text: str
    language: dict            # {"code": "en", "confidence": 0.99}
    academic: dict            # AcademicStructure.to_dict()
    processing_history: list[dict]
    validation: dict          # {"status": ..., "outcomes": [...]}
    stats: dict               # block counts by type, char count, etc.

    def to_dict(self) -> dict:
        return {
            "resource_id": self.resource_id,
            "metadata": self.resource.metadata.to_dict(),
            "content_blocks": [b.model_dump(mode="json") for b in self.resource.blocks],
            "clean_text": self.clean_text,
            "language": self.language,
            "academic_structure": self.academic,
            "processing_history": self.processing_history,
            "validation": self.validation,
            "stats": self.stats,
        }

    def save(self, derived_root: str | Path) -> Path:
        out_dir = Path(derived_root) / self.resource_id
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "package.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path


@dataclass
class IngestionResult:
    job_path: str
    status: IngestionStatus
    resource: LearningResource | None = None
    package: ResourcePackage | None = None
    outcomes: list[StageOutcome] = field(default_factory=list)

    @property
    def resource_id(self) -> str | None:
        return self.resource.resource_id if self.resource else None

    @property
    def ok(self) -> bool:
        return self.status in (IngestionStatus.SUCCESS, IngestionStatus.PARTIAL)

    @property
    def errors(self) -> list[StageOutcome]:
        return [o for o in self.outcomes if o.is_error]

    def summary(self) -> str:
        rid = self.resource_id or Path(self.job_path).name
        return f"[{self.status.value:<7}] {rid} ({len(self.errors)} error(s))"
