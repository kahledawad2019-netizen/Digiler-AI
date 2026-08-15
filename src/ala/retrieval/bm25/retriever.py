"""BM25Retriever — adapts BM25Index to the shared Retriever interface."""

from __future__ import annotations

from typing import Any

from ala.retrieval.bm25.index import BM25Index
from ala.retrieval.types import RetrievalResult


class BM25Retriever:
    def __init__(self, index: BM25Index) -> None:
        self.index = index

    def retrieve(self, query: str, *, top_k: int = 10,
                 filters: dict[str, Any] | None = None) -> list[RetrievalResult]:
        hits = self.index.search(query, top_k=top_k, filters=filters)
        return [
            RetrievalResult(
                chunk_id=cid, score=score, rank=i, source="bm25",
                payload=self.index.payload(cid), component_scores={"bm25": score},
            )
            for i, (cid, score) in enumerate(hits)
        ]
