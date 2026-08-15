"""Stage 13 — publication-quality evaluation figures, all from real results."""

from __future__ import annotations

from pathlib import Path

_SYS = {"dense": "#DD8452", "bm25": "#4C72B0", "hybrid": "#55A868", "graph": "#8172B3"}
_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "red": "#C44E52", "grey": "#937860"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rp = {r["retriever"]: r for r in payload["related_passage"]}
    ki = {r["retriever"]: r for r in payload["known_item"]}
    rag = payload["graphrag"]

    _system_comparison(plt, rp, figs)
    _radar(plt, rp, figs)
    _precision_recall(plt, ki, figs)
    _single_metric(plt, rp, "MRR", "MRR — related-passage", "mrr_comparison", figs)
    _single_metric(plt, rp, "nDCG@10", "nDCG@10 — related-passage", "ndcg_comparison", figs)
    _latency(plt, ki, figs)
    _throughput(plt, ki, figs)
    _grounding_comparison(plt, rag, figs)
    _citation_accuracy(plt, rag, figs)
    _context_composition(plt, rag, figs)
    _token_usage(plt, rag, figs)
    _hallucination(plt, rag, figs)
    _graph_coverage(plt, rag, figs)
    _multihop(plt, rag, figs)
    _ablation(plt, payload["ablation"], figs)
    _pipeline_summary(plt, payload, rp, rag, figs)


def _bars(plt, names, vals, colors, title, ylabel, path, ylim=None, fmt="{:.3f}"):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(names, vals, color=colors)
    ax.set_title(title); ax.set_ylabel(ylabel)
    if ylim:
        ax.set_ylim(*ylim)
    for i, v in enumerate(vals):
        ax.text(i, v, fmt.format(v), ha="center", va="bottom", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


def _system_comparison(plt, rp, figs):
    import numpy as np
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in rp]
    metrics = ["Hit@1", "Hit@5", "MRR", "nDCG@10"]
    x = np.arange(len(metrics))
    w = 0.2
    fig, ax = plt.subplots(figsize=(11, 6))
    for i, s in enumerate(systems):
        ax.bar(x + (i - 1.5) * w, [rp[s][m] for m in metrics], w, label=s.upper(), color=_SYS[s])
    ax.set_xticks(x); ax.set_xticklabels(metrics)
    ax.set_title("Retrieval system comparison — related-passage (semantic)")
    ax.set_ylabel("score"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "system_comparison.png", dpi=130); plt.close(fig)


def _radar(plt, rp, figs):
    import numpy as np
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in rp]
    axes = ["Hit@1", "Hit@5", "MRR", "nDCG@10", "Speed"]
    lat = {s: rp[s]["latency_ms"] for s in systems}
    max_lat = max(lat.values()) or 1.0
    ang = np.linspace(0, 2 * np.pi, len(axes), endpoint=False).tolist()
    ang += ang[:1]
    fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw=dict(polar=True))
    for s in systems:
        vals = [rp[s]["Hit@1"], rp[s]["Hit@5"], rp[s]["MRR"], rp[s]["nDCG@10"],
                1.0 - lat[s] / max_lat]
        vals += vals[:1]
        ax.plot(ang, vals, label=s.upper(), color=_SYS[s], linewidth=2)
        ax.fill(ang, vals, color=_SYS[s], alpha=0.08)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(axes)
    ax.set_ylim(0, 1); ax.set_title("Retrieval systems — multi-metric radar", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.25, 1.1))
    fig.tight_layout(); fig.savefig(figs / "radar.png", dpi=130); plt.close(fig)


def _precision_recall(plt, ki, figs):
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in ki]
    ks = [1, 5, 10]
    fig, ax = plt.subplots(figsize=(8, 6))
    for s in systems:
        ax.plot(ks, [ki[s][f"Hit@{k}"] for k in ks], "o-", label=s.upper(), color=_SYS[s], lw=2)
    ax.set_xticks(ks); ax.set_xlabel("k"); ax.set_ylabel("Hit@k")
    ax.set_title("Retrieval quality curve — Hit@k (known-item)"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "precision_recall.png", dpi=130); plt.close(fig)


def _single_metric(plt, rp, metric, title, fname, figs):
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in rp]
    _bars(plt, [s.upper() for s in systems], [rp[s][metric] for s in systems],
          [_SYS[s] for s in systems], title, metric, figs / f"{fname}.png", ylim=(0, 1.05))


def _latency(plt, ki, figs):
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in ki]
    _bars(plt, [s.upper() for s in systems], [ki[s]["latency_ms"] for s in systems],
          [_SYS[s] for s in systems], "Mean latency per query", "ms",
          figs / "latency_comparison.png", fmt="{:.1f}")


def _throughput(plt, ki, figs):
    systems = [s for s in ("dense", "bm25", "hybrid", "graph") if s in ki]
    _bars(plt, [s.upper() for s in systems], [ki[s]["qps"] for s in systems],
          [_SYS[s] for s in systems], "Throughput", "queries / sec",
          figs / "throughput_comparison.png", fmt="{:.1f}")


def _rag_pair(plt, rag, key, title, fname, figs, ylim=(0, 1.08), fmt="{:.3f}"):
    _bars(plt, ["graph-evid ON", "graph-evid OFF"],
          [rag["full"][key], rag["no_graph_evidence"][key]],
          [_C["green"], _C["grey"]], title, key, figs / f"{fname}.png", ylim=ylim, fmt=fmt)


def _grounding_comparison(plt, rag, figs):
    import numpy as np
    labels = ["grounding", "faithfulness", "citation_accuracy"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - 0.2, [rag["full"][k] for k in labels], 0.4, label="graph-evid ON", color=_C["green"])
    ax.bar(x + 0.2, [rag["no_graph_evidence"][k] for k in labels], 0.4, label="graph-evid OFF",
           color=_C["grey"])
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylim(0, 1.1)
    ax.set_title("GraphRAG grounding / faithfulness / citation accuracy"); ax.legend()
    for i, k in enumerate(labels):
        ax.text(i - 0.2, rag["full"][k], f'{rag["full"][k]:.2f}', ha="center", va="bottom", fontsize=8)
        ax.text(i + 0.2, rag["no_graph_evidence"][k], f'{rag["no_graph_evidence"][k]:.2f}',
                ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "grounding_comparison.png", dpi=130); plt.close(fig)


def _citation_accuracy(plt, rag, figs):
    _rag_pair(plt, rag, "citation_accuracy", "Citation accuracy (valid, resolvable citations)",
              "citation_accuracy", figs)


def _context_composition(plt, rag, figs):
    import numpy as np
    labels = ["context_precision", "context_recall", "multi_hop", "completeness"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x - 0.2, [rag["full"][k] for k in labels], 0.4, label="graph-evid ON", color=_C["green"])
    ax.bar(x + 0.2, [rag["no_graph_evidence"][k] for k in labels], 0.4, label="graph-evid OFF",
           color=_C["grey"])
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylim(0, 1.1)
    ax.set_title("GraphRAG context quality"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "context_composition.png", dpi=130); plt.close(fig)


def _token_usage(plt, rag, figs):
    _rag_pair(plt, rag, "tokens", "Context token usage", "token_usage", figs,
              ylim=None, fmt="{:.0f}")


def _hallucination(plt, rag, figs):
    _bars(plt, ["graph-evid ON", "graph-evid OFF"],
          [rag["full"]["hallucination"], rag["no_graph_evidence"]["hallucination"]],
          [_C["green"], _C["red"]], "Hallucination rate (1 − grounding)", "rate",
          figs / "hallucination_comparison.png", ylim=(0, max(0.05, rag["full"]["hallucination"] + 0.02)))


def _graph_coverage(plt, rag, figs):
    _bars(plt, ["context recall", "multi-hop rate", "citation acc."],
          [rag["full"]["context_recall"], rag["full"]["multi_hop"], rag["full"]["citation_accuracy"]],
          [_C["blue"], _C["purple"], _C["green"]], "GraphRAG graph coverage", "rate",
          figs / "graph_coverage.png", ylim=(0, 1.08))


def _multihop(plt, rag, figs):
    _rag_pair(plt, rag, "multi_hop", "Multi-hop reasoning presence (≥1 relation in context)",
              "multihop_analysis", figs)


def _ablation(plt, ablation, figs):
    arms = [a for a in ablation if "nDCG@10" in a]
    labels = [a["arm"].replace(" (", "\n(") for a in arms]
    vals = [a["nDCG@10"] for a in arms]
    colors = [_C["red"] if a["disables"] != "—" else _C["green"] for a in arms]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.bar(range(len(arms)), vals, color=colors)
    ax.set_xticks(range(len(arms))); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylabel("nDCG@10 (related-passage)")
    ax.set_title("Ablation — retrieval quality with each component disabled")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "ablation.png", dpi=130); plt.close(fig)


def _pipeline_summary(plt, payload, rp, rag, figs):
    best = max(rp, key=lambda s: rp[s]["nDCG@10"])
    lines = [
        "DIGILER AI — RETRIEVAL & GRAPHRAG PIPELINE (real corpus)",
        "",
        f"corpus graph: {payload['setup']['corpus_nodes']} nodes / {payload['setup']['corpus_edges']} edges",
        f"retrieval eval: {payload['setup']['n_retrieval']} queries   |   graphrag eval: {payload['setup']['n_graphrag']} questions",
        "",
        "RETRIEVAL (related-passage nDCG@10):",
        f"   dense {rp.get('dense',{}).get('nDCG@10','-')}   bm25 {rp.get('bm25',{}).get('nDCG@10','-')}"
        f"   hybrid {rp.get('hybrid',{}).get('nDCG@10','-')}   graph {rp.get('graph',{}).get('nDCG@10','-')}"
        f"   →  best: {best.upper()}",
        "",
        "GRAPHRAG (graph evidence ON):",
        f"   grounding {rag['full']['grounding']}   faithfulness {rag['full']['faithfulness']}"
        f"   citation acc {rag['full']['citation_accuracy']}   hallucination {rag['full']['hallucination']}",
        f"   context precision {rag['full']['context_precision']}   recall {rag['full']['context_recall']}"
        f"   multi-hop {rag['full']['multi_hop']}",
        "",
        "Generator: extractive-grounded (offline) — grounded by construction; LLM seam ready.",
    ]
    fig, ax = plt.subplots(figsize=(12, 6.5))
    ax.text(0.02, 0.98, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=11)
    ax.axis("off")
    ax.set_title("Retrieval pipeline summary", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "pipeline_summary.png", dpi=130); plt.close(fig)
