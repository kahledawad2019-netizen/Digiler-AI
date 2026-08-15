"""Stage 8 — retrieval evaluation metric tests."""

from __future__ import annotations

import math

from ala.retrieval.evaluation import metrics as M
from ala.retrieval.evaluation.evaluate import evaluate
from ala.retrieval.evaluation.evalset import EvalQuery
from ala.retrieval.search.types import RetrievalResult


def test_basic_metrics():
    ranked = ["a", "b", "c", "d"]
    rel = {"c"}
    assert M.hit_at_k(ranked, rel, 3) == 1.0 and M.hit_at_k(ranked, rel, 2) == 0.0
    assert M.reciprocal_rank(ranked, rel) == 1 / 3
    assert M.recall_at_k(ranked, rel, 3) == 1.0
    assert abs(M.precision_at_k(ranked, rel, 3) - 1 / 3) < 1e-9


def test_average_precision_and_ndcg():
    # relevant at ranks 1 and 3 -> AP = (1/1 + 2/3) / 2
    assert abs(M.average_precision(["a", "x", "c"], {"a", "c"}) - (1 + 2 / 3) / 2) < 1e-9
    # single relevant at rank 2 -> nDCG = (1/log2(3)) / (1/log2(2))
    assert abs(M.ndcg_at_k(["x", "a"], {"a"}, 2) - (1 / math.log2(3))) < 1e-9
    assert abs(M.ndcg_at_k(["a", "x"], {"a"}, 2) - 1.0) < 1e-9


def test_evaluate_aggregates():
    evalset = [EvalQuery("q1", "r1::c0", "r1"), EvalQuery("q2", "r2::c0", "r2")]
    resource_chunks = {"r1": {"r1::c0", "r1::c1"}, "r2": {"r2::c0"}}

    def perfect(query, top_k):
        gold = "r1::c0" if query == "q1" else "r2::c0"
        return [RetrievalResult(gold, 1.0, 0, "x", {"resource_id": gold.split("::")[0]})]

    r = evaluate("perfect", perfect, evalset, resource_chunks, k=10)
    assert r.hit1 == 1.0 and r.mrr == 1.0 and r.n_queries == 2 and r.qps >= 0
