"""IngestionPipeline — the orchestrator.

Runs the ordered stages for a resource with the cross-cutting concerns handled
in ONE place: timing, per-stage retry, structured-error capture, processing
history, and never letting one resource crash the batch. Stages stay pure.

Flow per resource:
    build metadata seed (Registry) -> [Stage 2..10] -> Registry/Catalog commit
"""

from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

from ala.config.settings import Settings
from ala.core.enums import ProcessingStatus, StageStatus
from ala.fabric.learning_resource import LearningResource
from ala.ingestion.config import PipelineConfig
from ala.ingestion.context import IngestionJob, PipelineContext, ResourceClassification
from ala.ingestion.discovery import ResourceDiscovery
from ala.ingestion.errors import OutcomeLevel, StageOutcome
from ala.ingestion.loaders.registry import default_loaders
from ala.ingestion.result import IngestionResult, IngestionStatus
from ala.ingestion.stages import (
    AcademicStructureStage,
    CleaningNormalizationStage,
    ContentExtractionStage,
    FileValidationStage,
    LanguageDetectionStage,
    LoaderSelectionStage,
    MetadataEnrichmentStage,
    ResourcePackagingStage,
    StructuralParsingStage,
)
from ala.ingestion.stages.base import PipelineStage
from ala.registry.registry import ResourceRegistry

log = logging.getLogger("ala.ingestion")


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        config: PipelineConfig,
        stages: list[PipelineStage],
        registry: ResourceRegistry,
    ) -> None:
        self.settings = settings
        self.config = config
        self.stages = stages
        self.registry = registry

    @classmethod
    def default(
        cls, settings: Settings, registry: ResourceRegistry | None = None
    ) -> "IngestionPipeline":
        """Wire the standard 9-stage chain (Stages 2-10) with default components."""
        config = PipelineConfig.from_settings(settings)
        loaders = default_loaders()
        stages: list[PipelineStage] = [
            FileValidationStage(),
            LoaderSelectionStage(loaders),
            ContentExtractionStage(),
            CleaningNormalizationStage(),
            LanguageDetectionStage(),
            StructuralParsingStage(),
            AcademicStructureStage(),
            MetadataEnrichmentStage(),
            ResourcePackagingStage(settings.derived_path),
        ]
        registry = registry or ResourceRegistry.from_settings(settings)
        return cls(settings, config, stages, registry)

    # ------------------------------------------------------------------ #
    def ingest_job(self, job: IngestionJob) -> IngestionResult:
        ctx = PipelineContext(self.settings, self.config, job)

        # Metadata seed (Stage 1 output already resolved into the job).
        try:
            meta = self._build_seed(job)
        except Exception as exc:  # noqa: BLE001 - report, never crash
            ctx.add_outcome("build_metadata", str(exc), level=OutcomeLevel.ERROR,
                            error_type=type(exc).__name__, recoverable=False)
            return IngestionResult(str(job.source_path), IngestionStatus.FAILED,
                                   outcomes=ctx.outcomes)

        resource = LearningResource.from_metadata(meta)
        status = IngestionStatus.SUCCESS

        for stage in self.stages:
            resource, failed = self._run_stage(stage, resource, ctx)
            if failed:
                if getattr(stage, "critical", False):
                    status = IngestionStatus.FAILED
                    resource.metadata.status.processing_status = ProcessingStatus.FAILED.value
                    break
                if status == IngestionStatus.SUCCESS:
                    status = IngestionStatus.PARTIAL

        # Registry Update -> Knowledge Catalog Update
        try:
            self.registry.commit(resource.metadata)
        except Exception as exc:  # noqa: BLE001
            ctx.add_outcome("commit", str(exc), level=OutcomeLevel.ERROR,
                            error_type=type(exc).__name__, recoverable=False)
            if status != IngestionStatus.FAILED:
                status = IngestionStatus.PARTIAL

        result = IngestionResult(
            job_path=str(job.source_path),
            status=status,
            resource=resource,
            package=ctx.analysis.get("package"),
            outcomes=ctx.outcomes,
        )
        log.info(result.summary())
        return result

    def ingest_path(
        self, path: str | Path, classification: ResourceClassification
    ) -> IngestionResult:
        return self.ingest_job(IngestionJob(Path(path), classification))

    def ingest_directory(self, root: str | Path | None = None) -> list[IngestionResult]:
        """Discover and ingest a tree. One resource failing never stops the rest."""
        results: list[IngestionResult] = []
        for job in ResourceDiscovery(self.settings).discover(root):
            try:
                results.append(self.ingest_job(job))
            except Exception as exc:  # noqa: BLE001 - absolute safety net
                log.exception("Unhandled error ingesting %s", job.source_path)
                results.append(
                    IngestionResult(
                        str(job.source_path), IngestionStatus.FAILED,
                        outcomes=[StageOutcome("pipeline", OutcomeLevel.ERROR, str(exc))],
                    )
                )
        return results

    # ------------------------------------------------------------------ #
    def _build_seed(self, job: IngestionJob):
        c = job.classification
        return self.registry.build_metadata(
            job.source_path,
            track=c.track, course=c.course, module=c.module, title=c.title,
            doc_type=c.doc_type, role=c.role,
            language=c.language or self.config.language.default,
            slug=c.slug, week=c.week, lecture=c.lecture, subject=c.subject,
            update=True,      # re-ingesting re-versions rather than erroring
            strict=False,     # the pipeline records issues; it doesn't raise on them
        )

    def _run_stage(
        self, stage: PipelineStage, resource: LearningResource, ctx: PipelineContext
    ) -> tuple[LearningResource, bool]:
        attempts = 1 + (self.config.max_retries if getattr(stage, "retryable", False) else 0)
        t0 = perf_counter()
        exc: Exception | None = None
        for _ in range(attempts):
            try:
                resource = stage.process(resource, ctx)
                exc = None
                break
            except Exception as e:  # noqa: BLE001 - structured capture below
                exc = e
        duration_ms = int((perf_counter() - t0) * 1000)

        if exc is None:
            resource.metadata.add_processing_step(
                stage.name, status=StageStatus.DONE, tool="ingestion", duration_ms=duration_ms
            )
            return resource, False

        ctx.add_outcome(stage.name, str(exc), level=OutcomeLevel.ERROR,
                        error_type=type(exc).__name__,
                        recoverable=not getattr(stage, "critical", False),
                        duration_ms=duration_ms)
        resource.metadata.add_processing_step(
            stage.name, status=StageStatus.FAILED, tool="ingestion",
            duration_ms=duration_ms, notes=str(exc),
        )
        return resource, True
