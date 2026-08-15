"""Stage 7 — Hybrid retrieval engine (dense + BM25 + RRF + optional reranker)."""

from ala.retrieval.search.config import RetrievalConfig
from ala.retrieval.search.dense import DenseRetriever
from ala.retrieval.search.factory import build_retrievers
from ala.retrieval.search.fusion import reciprocal_rank_fusion
from ala.retrieval.search.hybrid import HybridRetriever
from ala.retrieval.search.reranker import (
    CrossEncoderReranker,
    IdentityReranker,
    Reranker,
)
from ala.retrieval.search.types import RetrievalResult, Retriever

__all__ = [
    "RetrievalConfig",
    "RetrievalResult",
    "Retriever",
    "DenseRetriever",
    "HybridRetriever",
    "reciprocal_rank_fusion",
    "Reranker",
    "IdentityReranker",
    "CrossEncoderReranker",
    "build_retrievers",
]
