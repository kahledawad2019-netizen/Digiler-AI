"""Stage-5 benchmark report: scalability on real corpus vectors + charts.

Loads stored embeddings from the corpus, benchmarks Qdrant insert/search at
increasing collection sizes (in an ephemeral ``:memory:`` store so it never
touches the production index), and writes a Markdown report + charts to
``reports/stage5_qdrant/``.
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.embedding.store import EmbeddingStore
from ala.retrieval.vectorstore import benchmark as bench
from ala.retrieval.vectorstore.base import VectorPoint
from ala.retrieval.vectorstore.payload import build_payload
from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore


def load_corpus_points(settings: Settings, model_id: str, limit: int = 5000) -> list[VectorPoint]:
    derived = settings.derived_path
    chunk_store = ChunkStore(settings.derived_path)
    emb_store = EmbeddingStore(settings.derived_path)
    points: list[VectorPoint] = []
    for manifest in sorted(derived.glob(f"*/embeddings/{model_id}.manifest.json")):
        rid = manifest.parent.parent.name
        vectors = emb_store.load_vectors(rid, model_id)
        metas = {m.chunk_id: m for m in chunk_store.load_meta(rid, "child")}
        for cid, vec in vectors:
            if cid in metas:
                points.append(VectorPoint(chunk_id=cid, vector=vec, payload=build_payload(metas[cid])))
            if len(points) >= limit:
                return points
    return points


def run_report(settings: Settings, model_id: str = "hashing", *,
               limit: int = 5000, out_dir: str | Path | None = None) -> Path:
    points = load_corpus_points(settings, model_id, limit=limit)
    if not points:
        raise RuntimeError(f"No embeddings for model '{model_id}' — run `ala embed --all` first.")

    dim = len(points[0].vector)
    queries = [p.vector for p in points[:20]]
    sizes = [n for n in (500, 1000, 2000, 3000, 5000) if n <= len(points)] or [len(points)]

    store = QdrantVectorStore(":memory:", "bench", "cosine", dim=dim)
    results = bench.scalability_curve(store, points, queries, sizes)
    store.close()

    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage5_qdrant")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    _charts(results, figs)

    (out / "results.json").write_text(json.dumps([r.to_row() for r in results], indent=2), encoding="utf-8")
    (out / "README.md").write_text(_markdown(results, model_id, dim, len(points)), encoding="utf-8")
    return out


def _charts(results, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ns = [r.n_points for r in results]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    axes[0].plot(ns, [r.points_per_s for r in results], "o-", color="#4C72B0")
    axes[0].set_title("Insert throughput (points/s)"); axes[0].set_xlabel("collection size")
    axes[1].plot(ns, [r.search_ms_mean for r in results], "o-", color="#DD8452", label="mean")
    axes[1].plot(ns, [r.search_ms_p95 for r in results], "s--", color="#C44E52", label="p95")
    axes[1].set_title("Search latency (ms)"); axes[1].set_xlabel("collection size"); axes[1].legend()
    axes[2].plot(ns, [r.storage_mb for r in results], "o-", color="#55A868")
    axes[2].set_title("Vector storage (MB)"); axes[2].set_xlabel("collection size")
    fig.suptitle("Qdrant scalability on real corpus vectors")
    fig.tight_layout()
    fig.savefig(figs / "qdrant_scalability.png", dpi=130)
    plt.close(fig)


def _markdown(results, model_id, dim, n_points) -> str:
    return "\n".join([
        "# Stage 5 — Qdrant Vector Store: Benchmark",
        "",
        f"Model `{model_id}` · dim {dim} · {n_points} real corpus vectors · "
        "Qdrant local (`:memory:`) mode.",
        "",
        "## Scalability (insert throughput + search latency vs collection size)",
        "",
        bench.results_markdown(results),
        "",
        "`points/s` insert throughput · `search_ms`/`search_p95_ms` query latency at "
        "top-k · `peak_mb` peak Python allocation during insert · `storage_mb` raw vector "
        "bytes. Latencies are CPU-only local mode; a Qdrant server with HNSW tuning scales "
        "further.",
        "",
        "## Figures",
        "",
        "- ![scalability](figures/qdrant_scalability.png)",
        "",
    ])
