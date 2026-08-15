"""HybridRetriever — the complete query pipeline.

    query → normalize → (dense search ‖ BM25 search) → RRF fusion
          → [optional cross-encoder rerank] → top evidence

Dense and BM25 run independently and are fused by Reciprocal Rank Fusion with
configurable weights and ``rrf_k``. The cross-encoder reranker is optional
(config flag). Every result carries its per-component scores, so the ranking is
fully explainable downstream (Evidence Package, Stage 9).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from ala.retrieval.search.config import RetrievalConfig
from ala.retrieval.search.fusion import reciprocal_rank_fusion
from ala.retrieval.search.normalize import normalize_query
from ala.retrieval.search.reranker import IdentityReranker, Reranker
from ala.retrieval.search.types import RetrievalResult, Retriever


class HybridRetriever:
    def __init__(
        self,
        dense: Retriever | None,
        bm25: Retriever | None,
        config: RetrievalConfig | None = None,
        reranker: Reranker | None = None,
        text_resolver=None,
    ) -> None:
        self.dense = dense
        self.bm25 = bm25
        self.config = config or RetrievalConfig()
        self.reranker = reranker or IdentityReranker()
        self.text_resolver = text_resolver

    def retrieve(self, query: str, *, top_k: int | None = None,
                 filters: dict[str, Any] | None = None) -> list[RetrievalResult]:
        cfg = self.config
        top_k = top_k or cfg.top_k
        q = normalize_query(query)
        ck = cfg.candidate_k

        dense_res = self.dense.retrieve(q, top_k=ck, filters=filters) if self.dense else []
        bm25_res = self.bm25.retrieve(q, top_k=ck, filters=filters) if self.bm25 else []

        rrf = reciprocal_rank_fusion(
            [[r.chunk_id for r in dense_res], [r.chunk_id for r in bm25_res]],
            [cfg.dense_weight, cfg.bm25_weight], cfg.rrf_k,
        )

        payloads: dict[str, dict] = {}
        comp: dict[str, dict[str, float]] = defaultdict(dict)
        for r in dense_res:
            payloads[r.chunk_id] = r.payload
            comp[r.chunk_id]["dense"] = r.score
            comp[r.chunk_id]["dense_rank"] = r.rank + 1
        for r in bm25_res:
            payloads.setdefault(r.chunk_id, r.payload)
            comp[r.chunk_id]["bm25"] = r.score
            comp[r.chunk_id]["bm25_rank"] = r.rank + 1

        merged = sorted(rrf.items(), key=lambda kv: kv[1], reverse=True)
        results = [
            RetrievalResult(
                chunk_id=cid, score=score, rank=i, source="hybrid",
                payload=payloads.get(cid, {}), component_scores={**comp[cid], "rrf": score},
            )
            for i, (cid, score) in enumerate(merged)
        ]

        if cfg.rerank_enabled and not isinstance(self.reranker, IdentityReranker):
            candidates = results[: cfg.rerank_candidates]
            if self.text_resolver is not None:
                self.text_resolver.attach(candidates)
            return self.reranker.rerank(query, candidates, top_k)

        return results[:top_k]

    # explicit single-arm access for evaluation / CLI
    def retrieve_dense(self, query, *, top_k=None, filters=None):
        return self.dense.retrieve(normalize_query(query), top_k=top_k or self.config.top_k,
                                   filters=filters) if self.dense else []

    def retrieve_bm25(self, query, *, top_k=None, filters=None):
        return self.bm25.retrieve(normalize_query(query), top_k=top_k or self.config.top_k,
                                  filters=filters) if self.bm25 else []
