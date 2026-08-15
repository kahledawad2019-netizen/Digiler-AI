"""Standard information-retrieval metrics.

Each takes a ranked list of ids and a set of relevant ids. Pure functions, so
they are unit-tested directly against known cases.
"""

from __future__ import annotations

import math


def hit_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return 1.0 if set(ranked[:k]) & relevant else 0.0


def recall_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & relevant) / len(relevant)


def precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(set(ranked[:k]) & relevant) / k


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, d in enumerate(ranked):
        if d in relevant:
            return 1.0 / (i + 1)
    return 0.0


def average_precision(ranked: list[str], relevant: set[str]) -> float:
    if not relevant:
        return 0.0
    hits = 0
    total = 0.0
    for i, d in enumerate(ranked):
        if d in relevant:
            hits += 1
            total += hits / (i + 1)
    return total / len(relevant) if hits else 0.0


def dcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    return sum(1.0 / math.log2(i + 2) for i, d in enumerate(ranked[:k]) if d in relevant)


def ndcg_at_k(ranked: list[str], relevant: set[str], k: int) -> float:
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(k, len(relevant))))
    return dcg_at_k(ranked, relevant, k) / idcg if idcg else 0.0
