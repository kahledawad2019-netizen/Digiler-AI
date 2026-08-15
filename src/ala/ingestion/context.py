"""Ingestion job + shared per-run context.

A ``PipelineContext`` is the mutable scratch-space shared across stages of ONE
resource's run. Stages read/write it (selected loader, cross-stage analysis,
outcomes) so they stay decoupled from each other — they depend on the context,
not on each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ala.config.settings import Settings
from ala.core.enums import DocType, Role
from ala.ingestion.config import PipelineConfig
from ala.ingestion.errors import OutcomeLevel, StageOutcome


@dataclass
class ResourceClassification:
    """Where a resource sits in the taxonomy + how to describe it.

    Provided explicitly by the caller, or inferred from the managed folder
    layout by ResourceDiscovery.
    """

    track: str
    course: str
    module: str
    title: str
    doc_type: DocType = DocType.OTHER
    role: Role = Role.MATERIAL
    language: str | None = None
    week: int | None = None
    lecture: str | None = None
    slug: str | None = None
    subject: str | None = None


@dataclass
class IngestionJob:
    source_path: Path
    classification: ResourceClassification


@dataclass
class PipelineContext:
    settings: Settings
    config: PipelineConfig
    job: IngestionJob
    loader: Any = None                          # selected SourceAdapter (set by Stage 3)
    analysis: dict[str, Any] = field(default_factory=dict)   # cross-stage enrichment
    outcomes: list[StageOutcome] = field(default_factory=list)

    @property
    def source_path(self) -> Path:
        return self.job.source_path

    def add_outcome(
        self,
        stage: str,
        message: str,
        *,
        level: OutcomeLevel = OutcomeLevel.INFO,
        error_type: str | None = None,
        recoverable: bool = True,
        duration_ms: int | None = None,
        **detail: Any,
    ) -> StageOutcome:
        outcome = StageOutcome(
            stage=stage, level=level, message=message, error_type=error_type,
            recoverable=recoverable, duration_ms=duration_ms, detail=detail,
        )
        self.outcomes.append(outcome)
        return outcome
