"""Rerankers — an optional, plug-and-play final ranking stage.

``IdentityReranker`` is a real no-op (keeps fusion order) — the default when
reranking is disabled. ``CrossEncoderReranker`` scores (query, chunk-text) pairs
with a sentence-transformers cross-encoder (lazy import). Both satisfy the same
``Reranker`` interface, so enabling reranking is a config flag.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ala.retrieval.search.types import RetrievalResult


@runtime_checkable
class Reranker(Protocol):
    def rerank(self, query: str, results: list[RetrievalResult],
               top_k: int) -> list[RetrievalResult]:
        ...


class IdentityReranker:
    """Keeps the fused order. Not a mock — a valid no-op ranking."""

    def rerank(self, query, results, top_k):
        return results[:top_k]


class CrossEncoderReranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
                 device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, device=self.device)
        return self._model

    def rerank(self, query, results, top_k):
        scored = [r for r in results if r.text]
        if not scored:
            return results[:top_k]
        ce = self.model.predict([(query, r.text) for r in scored])
        for r, s in zip(scored, ce):
            r.component_scores["rerank"] = float(s)
            r.score = float(s)
        ranked = sorted(scored, key=lambda r: r.score, reverse=True)
        for i, r in enumerate(ranked):
            r.rank = i
            r.source = "hybrid+rerank"
        return ranked[:top_k]
