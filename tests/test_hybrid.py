"""Stage 7 — hybrid retrieval, fusion, dense adapter, reranker tests."""

from __future__ import annotations

from ala.retrieval.search import (
    DenseRetriever,
    HybridRetriever,
    RetrievalConfig,
    reciprocal_rank_fusion,
)
from ala.retrieval.search.reranker import IdentityReranker
from ala.retrieval.search.types import RetrievalResult


def test_rrf_ranks_shared_items_higher():
    scores = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]], [1.0, 1.0], rrf_k=60)
    assert abs(scores["a"] - scores["b"]) < 1e-9      # symmetric ranks
    assert scores["a"] > scores["c"]                   # in both beats in one


class _Fake:
    def __init__(self, ids):
        self.ids = ids

    def retrieve(self, query, *, top_k=10, filters=None):
        return [RetrievalResult(chunk_id=c, score=1.0 - i * 0.1, rank=i, source="x",
                                payload={"resource_id": c}) for i, c in enumerate(self.ids[:top_k])]


def test_hybrid_fuses_both_arms():
    h = HybridRetriever(_Fake(["a", "b", "c"]), _Fake(["c", "d", "a"]),
                        RetrievalConfig(top_k=3, candidate_k=10))
    res = h.retrieve("q", top_k=3)
    ids = [r.chunk_id for r in res]
    assert set(ids) <= {"a", "b", "c", "d"}
    assert ids[0] in ("a", "c")                        # appear in both lists
    assert res[0].source == "hybrid" and "rrf" in res[0].component_scores
    assert "dense" in res[0].component_scores and "bm25" in res[0].component_scores


def test_identity_reranker_is_noop():
    results = [RetrievalResult("a", 1.0, 0, "hybrid"), RetrievalResult("b", 0.5, 1, "hybrid")]
    assert [r.chunk_id for r in IdentityReranker().rerank("q", results, 1)] == ["a"]


def test_dense_retriever_over_qdrant():
    from ala.retrieval.embedding import HashingEmbedder
    from ala.retrieval.vectorstore import QdrantVectorStore, VectorPoint

    emb = HashingEmbedder(dim=384)
    store = QdrantVectorStore(":memory:", "c", "cosine")
    store.ensure_collection(384)
    docs = {"a": "foreign key primary key constraint",
            "b": "convolutional neural network pooling"}
    store.upsert([VectorPoint(cid, emb.embed_query(t), {"resource_id": cid})
                  for cid, t in docs.items()])
    res = DenseRetriever(emb, store).retrieve("primary key", top_k=2)
    assert res[0].chunk_id == "a" and res[0].source == "dense"
    store.close()
