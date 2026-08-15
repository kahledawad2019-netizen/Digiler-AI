"""Stages 2-4: File Validation, Loader Selection, Content Extraction."""

from __future__ import annotations

from ala.fabric.learning_resource import LearningResource
from ala.ingestion.context import PipelineContext
from ala.ingestion.errors import OutcomeLevel, ValidationFailedError
from ala.ingestion.loaders.registry import LoaderRegistry
from ala.ingestion.stages.base import BaseStage


class FileValidationStage(BaseStage):
    """Stage 2 — reject unreadable / oversized / unsupported files before work."""

    name = "file_validation"
    critical = True

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        path = ctx.source_path
        cfg = ctx.config
        if not path.is_file():
            raise ValidationFailedError(f"file not found: {path}")
        suffix = path.suffix.lower()
        if suffix not in cfg.supported_extensions:
            raise ValidationFailedError(f"unsupported extension: {suffix}")
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > cfg.max_file_mb:
            raise ValidationFailedError(
                f"file too large: {size_mb:.1f} MB > {cfg.max_file_mb} MB"
            )
        if path.stat().st_size == 0:
            ctx.add_outcome(self.name, "file is empty", level=OutcomeLevel.WARNING)
        ctx.add_outcome(self.name, f"validated ({size_mb:.2f} MB)")
        return resource


class LoaderSelectionStage(BaseStage):
    """Stage 3 — pick the loader for this file type (injected registry)."""

    name = "loader_selection"
    critical = True

    def __init__(self, loaders: LoaderRegistry) -> None:
        self.loaders = loaders

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        loader = self.loaders.select(ctx.source_path)
        ctx.loader = loader
        ctx.add_outcome(self.name, f"selected loader: {loader.name}", loader=loader.name)
        return resource


class ContentExtractionStage(BaseStage):
    """Stage 4 — run the selected loader to produce structured blocks."""

    name = "content_extraction"
    critical = True
    retryable = True

    def process(self, resource: LearningResource, ctx: PipelineContext) -> LearningResource:
        if ctx.loader is None:
            raise ValidationFailedError("no loader selected")
        loaded = ctx.loader.load(ctx.source_path, resource.metadata)
        if loaded.block_count == 0:
            ctx.add_outcome(
                self.name,
                "no content blocks extracted (possible scanned/empty file - OCR may be needed)",
                level=OutcomeLevel.WARNING,
            )
        else:
            ctx.add_outcome(self.name, f"extracted {loaded.block_count} blocks",
                            blocks=loaded.block_count)
        return loaded
