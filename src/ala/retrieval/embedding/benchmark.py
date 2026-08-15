"""Embedding benchmark utilities.

Measures the quantities the milestone requires — embedding time, throughput,
compute memory, dimension, per-vector storage, query latency — plus an intrinsic
*coherence* quality signal: how much more similar two chunks from the SAME
resource are than two from different resources (a label-free proxy for whether
the embedding captures document semantics). Requires numpy.
"""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass, field

from ala.retrieval.embedding.base import Embedder


@dataclass
class BenchmarkResult:
    model_id: str
    version: str
    dim: int
    n_texts: int
    embed_time_s: float
    texts_per_s: float
    peak_compute_mb: float
    bytes_per_vector: int
    storage_mb: float
    query_latency_ms: float
    coherence_gap: float | None = None      # intra-resource cos − inter-resource cos
    nn_purity: float | None = None          # frac. of chunks whose top-1 neighbor shares resource
    mean_norm: float = 1.0

    def to_row(self) -> dict:
        return {
            "model": self.model_id, "dim": self.dim, "n": self.n_texts,
            "embed_s": round(self.embed_time_s, 3),
            "texts/s": round(self.texts_per_s, 1),
            "compute_mb": round(self.peak_compute_mb, 1),
            "bytes/vec": self.bytes_per_vector,
            "query_ms": round(self.query_latency_ms, 2),
            "coherence": None if self.coherence_gap is None else round(self.coherence_gap, 4),
            "nn_purity": None if self.nn_purity is None else round(self.nn_purity, 4),
        }


def benchmark_embedder(
    embedder: Embedder,
    texts: list[str],
    *,
    labels: list[str] | None = None,
    queries: list[str] | None = None,
    batch_size: int = 32,
) -> BenchmarkResult:
    import numpy as np

    # Warm up: trigger lazy model load + graph warmup BEFORE timing, so embed_time
    # measures steady-state throughput, not one-time cold-start (fair across backends).
    embedder.embed_documents(texts[: min(4, len(texts))], batch_size=batch_size)

    tracemalloc.start()
    t0 = time.perf_counter()
    vectors = embedder.embed_documents(texts, batch_size=batch_size)
    embed_time = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    arr = np.asarray(vectors, dtype="float32")
    dim = arr.shape[1] if arr.ndim == 2 else embedder.dim

    q = queries or texts[: min(5, len(texts))]
    t0 = time.perf_counter()
    for x in q:
        embedder.embed_query(x)
    query_latency_ms = (time.perf_counter() - t0) / max(1, len(q)) * 1000

    return BenchmarkResult(
        model_id=embedder.model_id, version=embedder.version, dim=dim, n_texts=len(texts),
        embed_time_s=embed_time, texts_per_s=len(texts) / embed_time if embed_time else 0.0,
        peak_compute_mb=peak / (1024 * 1024),
        bytes_per_vector=dim * 4, storage_mb=arr.nbytes / (1024 * 1024),
        query_latency_ms=query_latency_ms,
        coherence_gap=_coherence_gap(arr, labels) if labels else None,
        nn_purity=_nn_purity(arr, labels) if labels else None,
        mean_norm=float(np.linalg.norm(arr, axis=1).mean()) if arr.size else 0.0,
    )


def compare_models(
    embedders: list[Embedder],
    texts: list[str],
    *,
    labels: list[str] | None = None,
    queries: list[str] | None = None,
) -> list[BenchmarkResult]:
    return [benchmark_embedder(e, texts, labels=labels, queries=queries) for e in embedders]


def results_markdown(results: list[BenchmarkResult]) -> str:
    rows = [r.to_row() for r in results]
    cols = ["model", "dim", "n", "embed_s", "texts/s", "compute_mb", "bytes/vec",
            "query_ms", "coherence", "nn_purity"]
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join([head, sep, *body])


def _coherence_gap(arr, labels: list[str]) -> float:
    """Mean cosine of same-label pairs minus mean cosine of different-label pairs.

    Vectors are L2-normalized, so cosine = dot product. Uses all pairs up to a
    cap for tractability.
    """
    import numpy as np

    n = min(len(labels), arr.shape[0], 400)
    a = arr[:n]
    lab = np.asarray(labels[:n])
    sims = a @ a.T
    same = lab[:, None] == lab[None, :]
    iu = np.triu_indices(n, k=1)
    same_pairs = sims[iu][same[iu]]
    diff_pairs = sims[iu][~same[iu]]
    if same_pairs.size == 0 or diff_pairs.size == 0:
        return 0.0
    return float(same_pairs.mean() - diff_pairs.mean())


def _nn_purity(arr, labels: list[str]) -> float:
    """Fraction of chunks whose nearest neighbor (excluding self) shares the label.

    A rank-based quality signal robust to a model's absolute cosine scale (unlike
    the raw cosine gap), so it compares fairly across models.
    """
    import numpy as np

    n = min(len(labels), arr.shape[0], 500)
    a = arr[:n]
    lab = np.asarray(labels[:n])
    sims = a @ a.T
    np.fill_diagonal(sims, -np.inf)          # exclude self
    nn = sims.argmax(axis=1)
    return float((lab[nn] == lab).mean())
