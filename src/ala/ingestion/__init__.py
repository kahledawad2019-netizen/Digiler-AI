"""Ingestion pipeline — the data-processing backbone of the platform.

Transforms any supported learning resource into a high-quality, structured
``LearningResource`` + ``ResourcePackage``. No embeddings, chunking, vectors,
graph, agents, or RL — those are later milestones.

Public surface:
    IngestionPipeline   - the staged orchestrator (build .default(settings))
    ResourceClassification / IngestionJob - describe a unit of work
    IngestionResult / IngestionStatus / ResourcePackage - outputs
    ResourceDiscovery   - Stage 1 (find + classify files)
"""

from ala.ingestion.context import IngestionJob, ResourceClassification
from ala.ingestion.discovery import ResourceDiscovery
from ala.ingestion.errors import (
    IngestionError,
    LoaderError,
    StageOutcome,
    UnsupportedResourceError,
)
from ala.ingestion.pipeline import IngestionPipeline
from ala.ingestion.result import IngestionResult, IngestionStatus, ResourcePackage

__all__ = [
    "IngestionPipeline",
    "ResourceClassification",
    "IngestionJob",
    "ResourceDiscovery",
    "IngestionResult",
    "IngestionStatus",
    "ResourcePackage",
    "StageOutcome",
    "IngestionError",
    "LoaderError",
    "UnsupportedResourceError",
]
