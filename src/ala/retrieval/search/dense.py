"""DenseRetriever — embeds the query and searches the existing Qdrant store.

Uses the current embedding + vector-store APIs unchanged (does not rebuild
vectors). Just an adapter onto the shared Retriever interface.
"""

from __future__ import annotations

from typing import Any

from ala.retrieval.embedding.base import Embedder
from ala.retrieval.search.types import RetrievalResult
from ala.retrieval.vectorstore.base import VectorStore


class DenseRetriever:
    def __init__(self, embedder: Embedder, vector_store: VectorStore) -> None:
        self.embedder = embedder
        self.vector_store = vector_store

    def retrieve(self, query: str, *, top_k: int = 10,
                 filters: dict[str, Any] | None = None) -> list[RetrievalResult]:
        qv = self.embedder.embed_query(query)
        hits = self.vector_store.search(qv, top_k=top_k, filters=filters)
        return [
            RetrievalResult(
                chunk_id=h.chunk_id, score=float(h.score), rank=i, source="dense",
                payload=h.payload, component_scores={"dense": float(h.score)},
            )
            for i, h in enumerate(hits)
        ]
