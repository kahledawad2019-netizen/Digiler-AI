"""Vector-store benchmark: insert speed, search latency, memory, storage, scalability."""

from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass

from ala.retrieval.vectorstore.base import VectorPoint, VectorStore


@dataclass
class VSBenchmarkResult:
    n_points: int
    dim: int
    top_k: int
    insert_s: float
    points_per_s: float
    search_ms_mean: float
    search_ms_p95: float
    peak_mb: float
    storage_mb: float

    def to_row(self) -> dict:
        return {
            "n": self.n_points, "dim": self.dim, "top_k": self.top_k,
            "insert_s": round(self.insert_s, 3),
            "points/s": round(self.points_per_s, 1),
            "search_ms": round(self.search_ms_mean, 2),
            "search_p95_ms": round(self.search_ms_p95, 2),
            "peak_mb": round(self.peak_mb, 1),
            "storage_mb": round(self.storage_mb, 2),
        }


def benchmark_vector_store(
    store: VectorStore, points: list[VectorPoint], queries: list[list[float]],
    *, top_k: int = 10, batch_size: int = 256, recreate: bool = True,
) -> VSBenchmarkResult:
    import numpy as np

    dim = len(points[0].vector)
    store.ensure_collection(dim, recreate=recreate)

    tracemalloc.start()
    t0 = time.perf_counter()
    store.upsert(points, batch_size=batch_size)
    insert_s = time.perf_counter() - t0
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        store.search(q, top_k=top_k)
        latencies.append((time.perf_counter() - t0) * 1000)
    lat = np.asarray(latencies) if latencies else np.zeros(1)

    return VSBenchmarkResult(
        n_points=len(points), dim=dim, top_k=top_k,
        insert_s=insert_s, points_per_s=len(points) / insert_s if insert_s else 0.0,
        search_ms_mean=float(lat.mean()), search_ms_p95=float(np.percentile(lat, 95)),
        peak_mb=peak / (1024 * 1024), storage_mb=len(points) * dim * 4 / (1024 * 1024),
    )


def scalability_curve(
    store: VectorStore, points: list[VectorPoint], queries: list[list[float]],
    sizes: list[int], *, top_k: int = 10,
) -> list[VSBenchmarkResult]:
    """Benchmark at increasing collection sizes (insert throughput + search latency)."""
    out = []
    for n in sizes:
        subset = points[:n]
        if not subset:
            continue
        out.append(benchmark_vector_store(store, subset, queries, top_k=top_k, recreate=True))
    return out


def results_markdown(results: list[VSBenchmarkResult]) -> str:
    rows = [r.to_row() for r in results]
    cols = ["n", "dim", "top_k", "insert_s", "points/s", "search_ms", "search_p95_ms",
            "peak_mb", "storage_mb"]
    head = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join([head, sep, *body])
