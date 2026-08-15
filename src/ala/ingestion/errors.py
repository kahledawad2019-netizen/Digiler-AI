"""Structured errors and per-stage outcomes for the ingestion pipeline.

A resource never crashes the whole run. Every stage produces structured
outcomes; the orchestrator decides whether an outcome is fatal (critical stage)
or survivable (partial success).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ala.core.exceptions import AlaError


class IngestionError(AlaError):
    """Base for ingestion-specific failures."""


class UnsupportedResourceError(IngestionError):
    """No loader can handle the resource (unknown/unsupported type)."""


class LoaderError(IngestionError):
    """A loader failed to extract content (corrupt file, missing dependency…)."""


class ValidationFailedError(IngestionError):
    """File validation rejected the resource before extraction."""


class OutcomeLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class StageOutcome:
    """The structured result of running one stage on one resource."""

    stage: str
    level: OutcomeLevel = OutcomeLevel.INFO
    message: str = ""
    error_type: str | None = None
    recoverable: bool = True
    duration_ms: int | None = None
    detail: dict = field(default_factory=dict)

    @property
    def is_error(self) -> bool:
        return self.level is OutcomeLevel.ERROR

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "level": self.level.value,
            "message": self.message,
            "error_type": self.error_type,
            "recoverable": self.recoverable,
            "duration_ms": self.duration_ms,
            "detail": self.detail,
        }
