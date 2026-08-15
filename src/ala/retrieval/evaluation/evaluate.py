"""Evaluate a retriever over the known-item eval set.

Relevance = "chunk from the same source resource as the query's origin". Reports
Hit@k, Recall@10, Precision@5, MRR, MAP, nDCG@10 (all against that relevant set)
plus mean latency and throughput (queries/sec).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from ala.retrieval.evaluation import metrics as M
from ala.retrieval.evaluation.evalset import EvalQuery


@dataclass
class EvalResult:
    name: str
    n_queries: int
    hit1: float
    hit5: float
    hit10: float
    recall10: float
    precision5: float
    mrr: float
    map: float
    ndcg10: float
    mean_latency_ms: float
    qps: float

    def to_row(self) -> dict:
        return {
            "retriever": self.name, "n": self.n_queries,
            "Hit@1": round(self.hit1, 3), "Hit@5": round(self.hit5, 3),
            "Hit@10": round(self.hit10, 3), "Recall@10": round(self.recall10, 3),
            "P@5": round(self.precision5, 3), "MRR": round(self.mrr, 3),
            "MAP": round(self.map, 3), "nDCG@10": round(self.ndcg10, 3),
            "latency_ms": round(self.mean_latency_ms, 2), "qps": round(self.qps, 1),
        }


def evaluate(
    name: str,
    retrieve_fn: Callable[..., list],
    evalset: list[EvalQuery],
    resource_chunks: dict[str, set[str]],
    k: int = 10,
    exclude_gold_chunk: bool = False,
) -> EvalResult:
    """Evaluate a retriever.

    ``exclude_gold_chunk`` switches from known-item (find the exact source chunk)
    to **related-passage** retrieval: the source chunk is removed from both the
    relevant set and the results, so the task becomes "find the resource's OTHER
    passages" — a semantically meaningful task where dense retrieval helps.
    """
    import numpy as np

    acc = dict(hit1=0.0, hit5=0.0, hit10=0.0, rec10=0.0, prec5=0.0, mrr=0.0, ap=0.0, ndcg=0.0)
    latencies: list[float] = []
    for q in evalset:
        relevant = set(resource_chunks.get(q.gold_resource_id) or {q.gold_chunk_id})
        if exclude_gold_chunk:
            relevant.discard(q.gold_chunk_id)
            if not relevant:
                continue
        t0 = time.perf_counter()
        results = retrieve_fn(q.query, top_k=k + (1 if exclude_gold_chunk else 0))
        latencies.append((time.perf_counter() - t0) * 1000)
        ranked = [r.chunk_id for r in results if r.chunk_id != q.gold_chunk_id][:k] \
            if exclude_gold_chunk else [r.chunk_id for r in results]
        acc["hit1"] += M.hit_at_k(ranked, relevant, 1)
        acc["hit5"] += M.hit_at_k(ranked, relevant, 5)
        acc["hit10"] += M.hit_at_k(ranked, relevant, 10)
        acc["rec10"] += M.recall_at_k(ranked, relevant, 10)
        acc["prec5"] += M.precision_at_k(ranked, relevant, 5)
        acc["mrr"] += M.reciprocal_rank(ranked, relevant)
        acc["ap"] += M.average_precision(ranked, relevant)
        acc["ndcg"] += M.ndcg_at_k(ranked, relevant, 10)

    n = max(1, len(evalset))
    mean_lat = float(np.mean(latencies)) if latencies else 0.0
    return EvalResult(
        name=name, n_queries=len(evalset),
        hit1=acc["hit1"] / n, hit5=acc["hit5"] / n, hit10=acc["hit10"] / n,
        recall10=acc["rec10"] / n, precision5=acc["prec5"] / n,
        mrr=acc["mrr"] / n, map=acc["ap"] / n, ndcg10=acc["ndcg"] / n,
        mean_latency_ms=mean_lat, qps=1000.0 / mean_lat if mean_lat else 0.0,
    )


def results_markdown(results: list[EvalResult]) -> str:
    rows = [r.to_row() for r in results]
    cols = ["retriever", "n", "Hit@1", "Hit@5", "Hit@10", "Recall@10", "P@5",
            "MRR", "MAP", "nDCG@10", "latency_ms", "qps"]
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join([head, sep, *body])
