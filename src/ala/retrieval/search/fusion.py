"""Reciprocal Rank Fusion (RRF).

Combines several ranked lists into one, using only ranks (scale-free, so dense
cosine and BM25 scores fuse without normalization):

    RRF(d) = Σ_r  weight_r / (rrf_k + rank_r(d))      (rank 1-based)

``rrf_k`` (default 60) damps the contribution of low ranks.
"""

from __future__ import annotations

from collections import defaultdict


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    weights: list[float] | None = None,
    rrf_k: int = 60,
) -> dict[str, float]:
    weights = weights if weights is not None else [1.0] * len(rankings)
    scores: dict[str, float] = defaultdict(float)
    for ranking, weight in zip(rankings, weights):
        for rank, doc_id in enumerate(ranking):
            scores[doc_id] += weight / (rrf_k + rank + 1)
    return dict(scores)
