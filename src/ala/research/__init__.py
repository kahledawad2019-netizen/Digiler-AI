"""Stage 14 — Research Mode + Web Search Integration.

Extends the GraphRAG pipeline with a confidence gate: when the Knowledge Base
cannot confidently answer, Research Mode searches the web (provider abstraction),
scores + ranks sources, parses them into the **existing** Resource Fabric, merges
web evidence with KB evidence (provenance preserved), answers, and — on user
approval — grows the Knowledge Base through the **existing** ingestion pipeline
(DIR → chunking → metadata → embedding → Qdrant → BM25 → concept graph). No part
of the pipeline is duplicated; every component is additive.
"""

from ala.research.confidence import ConfidenceEstimator
from ala.research.controller import ResearchModeController
from ala.research.ingest import IncrementalIngestor
from ala.research.merge import ResearchEvidenceMerger
from ala.research.models import (ConfidenceLevel, ConfidenceReport, ResearchConfig,
                                 ResearchResult, SourceScore, WebResult)
from ala.research.search import WebSearchAdapter
from ala.research.sources import SourceQualityEvaluator

__all__ = [
    "ConfidenceEstimator", "ResearchModeController", "IncrementalIngestor",
    "ResearchEvidenceMerger", "WebSearchAdapter", "SourceQualityEvaluator",
    "ConfidenceReport", "ConfidenceLevel", "ResearchConfig", "ResearchResult",
    "SourceScore", "WebResult",
]
