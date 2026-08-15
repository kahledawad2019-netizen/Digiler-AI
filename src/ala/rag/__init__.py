"""Stage 12 — GraphRAG.

The generation layer on top of the retrieval engine. Orchestrates:

    question → GraphRetriever → GraphEvidenceMerger → EvidencePackage
             → GraphContextBuilder → GraphPromptBuilder → LLM → grounded answer

The LLM **only** ever sees the structured prompt built from the Evidence Package
— never raw retrieval output (V3 hard rule). Every answer carries citations, a
reasoning trace and a grounding check, so nothing is hallucinated.
"""

from ala.rag.citations import GraphCitationManager
from ala.rag.context import GraphContextBuilder
from ala.rag.llm import ExtractiveGroundedGenerator, LLMClient
from ala.rag.merger import GraphEvidenceMerger
from ala.rag.models import (CitationRecord, GraphRAGAnswer, GraphRAGConfig,
                            ReasoningContext)
from ala.rag.pipeline import GraphRAGPipeline, GraphRAGService
from ala.rag.prompt import GraphPromptBuilder

__all__ = [
    "GraphCitationManager", "GraphContextBuilder", "GraphEvidenceMerger",
    "GraphPromptBuilder", "LLMClient", "ExtractiveGroundedGenerator",
    "GraphRAGPipeline", "GraphRAGService", "ReasoningContext",
    "GraphRAGAnswer", "GraphRAGConfig", "CitationRecord",
]
