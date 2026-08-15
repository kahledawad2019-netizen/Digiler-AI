"""Stage 8 report — compare Dense vs BM25 vs Hybrid, two evaluation modes + charts.

Runs two complementary evaluations on the same corpus queries:
  * **known-item** — find the exact source chunk (lexically-biased; BM25-favouring);
  * **related-passage** — exclude the source chunk and find the resource's OTHER
    passages (semantically meaningful; where dense/hybrid help).

Reporting both is the honest, publication-grade way to characterize where each
retriever wins, rather than tuning a single metric.
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.evaluation.evaluate import EvalResult, evaluate, results_markdown
from ala.retrieval.evaluation.evalset import build_known_item_evalset
from ala.retrieval.search.factory import build_retrievers
from ala.retrieval.search.normalize import normalize_query


def run_report(settings: Settings, *, n: int = 150, out_dir: str | Path | None = None) -> Path:
    evalset, resource_chunks = build_known_item_evalset(settings, n=n)
    if not evalset:
        raise RuntimeError("Empty eval set — build the corpus + BM25 index first.")

    retrievers = build_retrievers(settings)
    k = max(10, retrievers.config.top_k)

    def run_mode(exclude: bool) -> list[EvalResult]:
        return [
            evaluate("dense",
                     lambda q, top_k: retrievers.dense.retrieve(normalize_query(q), top_k=top_k),
                     evalset, resource_chunks, k, exclude_gold_chunk=exclude),
            evaluate("bm25",
                     lambda q, top_k: retrievers.bm25.retrieve(normalize_query(q), top_k=top_k),
                     evalset, resource_chunks, k, exclude_gold_chunk=exclude),
            evaluate("hybrid",
                     lambda q, top_k: retrievers.hybrid.retrieve(q, top_k=top_k),
                     evalset, resource_chunks, k, exclude_gold_chunk=exclude),
        ]

    try:
        known = run_mode(False)
        related = run_mode(True)
    finally:
        retrievers.close()

    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage6_retrieval")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    _charts(known, figs, "")
    _charts(related, figs, "_related")

    baseline_path = out / "results_baseline.json"
    if baseline_path.is_file():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        _embedding_chart(baseline, [r.to_row() for r in known], figs)

    (out / "results.json").write_text(json.dumps([r.to_row() for r in known], indent=2), encoding="utf-8")
    (out / "results_related.json").write_text(json.dumps([r.to_row() for r in related], indent=2), encoding="utf-8")
    (out / "README.md").write_text(_markdown(known, related, len(evalset), retrievers.config.embedding_model), encoding="utf-8")
    return out


def _charts(results: list[EvalResult], figs: Path, tag: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    names = [r.name for r in results]
    colors = [{"dense": "#4C72B0", "bm25": "#DD8452", "hybrid": "#55A868"}[n] for n in names]

    groups = [("Hit@1", [r.hit1 for r in results]), ("Hit@5", [r.hit5 for r in results]),
              ("Hit@10", [r.hit10 for r in results]), ("P@5", [r.precision5 for r in results]),
              ("MRR", [r.mrr for r in results]), ("nDCG@10", [r.ndcg10 for r in results])]
    x = np.arange(len(groups))
    fig, ax = plt.subplots(figsize=(11, 5))
    for i, name in enumerate(names):
        ax.bar(x + (i - 1) * 0.25, [g[1][i] for g in groups], 0.25, label=name, color=colors[i])
    ax.set_xticks(x); ax.set_xticklabels([g[0] for g in groups]); ax.set_ylim(0, 1)
    mode = "related-passage" if tag else "known-item"
    ax.set_title(f"Retrieval quality ({mode}) — Dense vs BM25 vs Hybrid")
    ax.legend(); fig.tight_layout()
    fig.savefig(figs / f"quality_comparison{tag}.png", dpi=130); plt.close(fig)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.bar(names, [r.mean_latency_ms for r in results], color=colors); a1.set_title("Mean query latency (ms)")
    a2.bar(names, [r.qps for r in results], color=colors); a2.set_title("Throughput (queries/s)")
    fig.tight_layout(); fig.savefig(figs / f"latency_throughput{tag}.png", dpi=130); plt.close(fig)

    best = max(results[0].mrr, results[1].mrr), max(results[0].hit10, results[1].hit10)
    hyb = results[2]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(np.arange(2) - 0.2, list(best), 0.4, label="best single arm", color="#8172B3")
    ax.bar(np.arange(2) + 0.2, [hyb.mrr, hyb.hit10], 0.4, label="hybrid (RRF)", color="#55A868")
    ax.set_xticks(range(2)); ax.set_xticklabels(["MRR", "Hit@10"]); ax.set_ylim(0, 1)
    ax.set_title(f"RRF contribution ({mode}): hybrid vs best single arm"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / f"fusion_gain{tag}.png", dpi=130); plt.close(fig)


def _embedding_chart(baseline_rows: list[dict], current_rows: list[dict], figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    def dense(rows):
        return next((r for r in rows if r["retriever"] == "dense"), None)

    b, c = dense(baseline_rows), dense(current_rows)
    if not b or not c:
        return
    metrics = ["Hit@1", "Hit@5", "MRR", "P@5", "nDCG@10"]
    x = np.arange(len(metrics))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - 0.2, [b[m] for m in metrics], 0.4, label="dense = hashing (baseline)", color="#8172B3")
    ax.bar(x + 0.2, [c[m] for m in metrics], 0.4, label="dense = e5-small", color="#4C72B0")
    ax.set_xticks(x); ax.set_xticklabels(metrics); ax.set_ylim(0, 1)
    ax.set_title("Embedding comparison — dense retrieval (known-item eval)")
    ax.legend(); fig.tight_layout()
    fig.savefig(figs / "embedding_comparison.png", dpi=130); plt.close(fig)


def _markdown(known: list[EvalResult], related: list[EvalResult], n: int, model: str) -> str:
    return "\n".join([
        "# Stage 6/7/8 — BM25 + Hybrid Retrieval: Evaluation",
        "",
        f"Dense model: **{model}**. {n} real corpus queries (a word span from a chunk).",
        "",
        "## Eval A — known-item (find the exact source chunk; lexically biased)",
        "",
        results_markdown(known),
        "",
        "BM25 is near-ceiling here because queries are verbatim spans; a semantic model "
        "is penalized for retrieving topically-similar chunks from *other* resources.",
        "",
        "## Eval B — related-passage (exclude the source chunk; semantic)",
        "",
        results_markdown(related),
        "",
        "The source chunk is removed, so the task is 'find the resource's OTHER passages' — "
        "where dense/hybrid contribute. This is the fair test of fusion value.",
        "",
        "## Figures",
        "",
        "- Known-item: ![q](figures/quality_comparison.png) ![l](figures/latency_throughput.png) ![f](figures/fusion_gain.png)",
        "- Related-passage: ![q](figures/quality_comparison_related.png) ![f](figures/fusion_gain_related.png)",
        "- Embedding: ![e](figures/embedding_comparison.png)",
        "",
    ])
