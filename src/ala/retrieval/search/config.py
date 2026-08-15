"""Hybrid retrieval configuration (from platform.yaml `retrieval.hybrid`)."""

from __future__ import annotations

from pydantic import BaseModel

from ala.config.settings import Settings


class RetrievalConfig(BaseModel):
    embedding_model: str = "hashing"
    top_k: int = 10
    candidate_k: int = 50
    dense_weight: float = 1.0
    bm25_weight: float = 1.0
    rrf_k: int = 60
    rerank_enabled: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    rerank_candidates: int = 50

    @classmethod
    def from_settings(cls, settings: Settings) -> "RetrievalConfig":
        return cls(**(settings.retrieval or {}).get("hybrid", {}))


class BM25FileConfig(BaseModel):
    location: str = "data/bm25/chunks"
    k1: float = 1.5
    b: float = 0.75
    min_token_len: int = 2

    @classmethod
    def from_settings(cls, settings: Settings) -> "BM25FileConfig":
        return cls(**(settings.retrieval or {}).get("bm25", {}))
