"""Pipeline stages (each independently testable, resource-in / resource-out)."""

from ala.ingestion.stages.base import BaseStage, PipelineStage
from ala.ingestion.stages.preprocessing import (
    ContentExtractionStage,
    FileValidationStage,
    LoaderSelectionStage,
)
from ala.ingestion.stages.processing import (
    CleaningNormalizationStage,
    LanguageDetectionStage,
    StructuralParsingStage,
)
from ala.ingestion.stages.enrichment import (
    AcademicStructureStage,
    MetadataEnrichmentStage,
    ResourcePackagingStage,
)

__all__ = [
    "PipelineStage",
    "BaseStage",
    "FileValidationStage",
    "LoaderSelectionStage",
    "ContentExtractionStage",
    "CleaningNormalizationStage",
    "LanguageDetectionStage",
    "StructuralParsingStage",
    "AcademicStructureStage",
    "MetadataEnrichmentStage",
    "ResourcePackagingStage",
]
