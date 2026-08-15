"""Pipeline stage contract.

Every stage receives a ``LearningResource`` and a ``PipelineContext`` and returns
a (possibly updated) ``LearningResource``. Stages never call each other — they
communicate only through the resource and the context, so any stage can be
replaced or reordered (Liskov / Open-Closed). Cross-cutting concerns (timing,
error capture, processing-history) are handled once by the orchestrator, not in
each stage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ala.fabric.learning_resource import LearningResource
from ala.ingestion.context import PipelineContext


@runtime_checkable
class PipelineStage(Protocol):
    name: str
    critical: bool      # if True, a failure aborts this resource (status=failed)
    retryable: bool     # if True, the orchestrator retries on failure

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource: ...


class BaseStage:
    """Convenience base with sane defaults."""

    name: str = "base"
    critical: bool = False
    retryable: bool = False

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        raise NotImplementedError
