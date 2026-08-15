"""Stage 14 — presentation-quality Research-Mode figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"kb": "#4C72B0", "web": "#DD8452", "in": "#55A868", "out": "#C44E52",
      "purple": "#8172B3", "grey": "#937860"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _pipeline(plt, figs)
    _confidence_distribution(plt, payload["confidence_gate"], figs)
    _confidence_histogram(plt, payload["confidence_gate"], figs)
    _gate_outcomes(plt, payload["confidence_gate"], figs)
    _source_authority(plt, payload["source_quality"], figs)
    _web_vs_kb(plt, payload["merge"], figs)
    _incremental_timeline(plt, payload["incremental_indexing"], figs)
    _knowledge_growth(plt, payload["incremental_indexing"], figs)


def _pipeline(plt, figs):
    steps = ["Question", "GraphRAG\n(KB)", "Confidence", "Web\nSearch", "Score +\nRank Sources",
             "Merge\nKB + Web", "Answer", "Ask to\nSave?", "Incremental\nIngest"]
    colors = [_C["grey"], _C["kb"], _C["purple"], _C["web"], _C["web"], _C["web"],
              _C["in"], _C["purple"], _C["kb"]]
    fig, ax = plt.subplots(figsize=(16, 3))
    for i, (s, c) in enumerate(zip(steps, colors)):
        ax.add_patch(plt.Rectangle((i * 1.75, 0), 1.45, 1.3, color=c, alpha=0.9))
        ax.text(i * 1.75 + 0.72, 0.65, s, ha="center", va="center", color="white",
                fontsize=8.5, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i * 1.75 + 1.72, 0.65), xytext=(i * 1.75 + 1.45, 0.65),
                        arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(3 * 1.75, -0.5, "confidence < threshold → web fallback (else answer directly from KB)",
            fontsize=9, style="italic")
    ax.set_xlim(-0.2, len(steps) * 1.75); ax.set_ylim(-0.8, 1.5); ax.axis("off")
    ax.set_title("Research Mode pipeline (Stage 14)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "research_pipeline.png", dpi=130); plt.close(fig)


def _confidence_distribution(plt, c, figs):
    import numpy as np
    fig, ax = plt.subplots(figsize=(8, 5))
    for i, (label, key, col) in enumerate([("in-corpus", "in_scores", _C["in"]),
                                           ("out-of-corpus", "out_scores", _C["out"])]):
        ys = c[key]
        xs = np.random.default_rng(i).normal(i, 0.05, len(ys))
        ax.scatter(xs, ys, color=col, alpha=0.8, s=60, label=label)
    ax.axhline(c["threshold"], color="black", linestyle="--", label=f"threshold {c['threshold']}")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["in-corpus", "out-of-corpus"])
    ax.set_ylabel("KB confidence"); ax.set_ylim(0, 1)
    ax.set_title(f"Confidence gate — separation AUC {c['separation_auc']}, "
                 f"gate accuracy {c['gate_accuracy']}"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "confidence_distribution.png", dpi=130); plt.close(fig)


def _confidence_histogram(plt, c, figs):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(c["in_scores"], bins=8, alpha=0.7, color=_C["in"], label="in-corpus")
    ax.hist(c["out_scores"], bins=8, alpha=0.7, color=_C["out"], label="out-of-corpus")
    ax.axvline(c["threshold"], color="black", linestyle="--", label=f"threshold {c['threshold']}")
    ax.set_xlabel("KB confidence"); ax.set_ylabel("questions")
    ax.set_title("Confidence distribution"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "confidence_histogram.png", dpi=130); plt.close(fig)


def _gate_outcomes(plt, c, figs):
    import numpy as np
    groups = ["in-corpus", "out-of-corpus"]
    research = [c["in_needs_research_rate"], c["out_needs_research_rate"]]
    kb = [1 - r for r in research]
    x = np.arange(2)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(x, kb, 0.5, label="answered from KB", color=_C["kb"])
    ax.bar(x, research, 0.5, bottom=kb, label="escalated to web", color=_C["web"])
    ax.set_xticks(x); ax.set_xticklabels(groups); ax.set_ylim(0, 1.05)
    ax.set_ylabel("fraction of questions"); ax.set_title("Confidence-gate routing")
    ax.legend()
    fig.tight_layout(); fig.savefig(figs / "gate_outcomes.png", dpi=130); plt.close(fig)


def _source_authority(plt, s, figs):
    ranked = s["ranked"]
    labels = [r["domain"][:24] for r in ranked][::-1]
    trust = [r["trust"] for r in ranked][::-1]
    colors = [(_C["out"] if r["duplicate"] or r["spam"] > 0.3 else _C["in"]) for r in ranked][::-1]
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(labels, trust, color=colors)
    ax.set_xlabel("trust score"); ax.set_xlim(0, 1)
    ax.set_title("Source authority / trust (red = duplicate or spam)")
    for i, v in enumerate(trust):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "source_authority.png", dpi=130); plt.close(fig)


def _web_vs_kb(plt, m, figs):
    fig, ax = plt.subplots(figsize=(6, 5))
    vals = [m.get("n_kb_items") or 0, m.get("n_web_items") or 0]
    ax.bar(["KB evidence", "web evidence"], vals, color=[_C["kb"], _C["web"]])
    ax.set_title("Merged evidence contribution"); ax.set_ylabel("evidence items")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "web_vs_kb.png", dpi=130); plt.close(fig)


def _incremental_timeline(plt, ix, figs):
    t = ix["timings_ms"]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(list(t.keys()), list(t.values()), color=_C["purple"])
    ax.set_title(f"Incremental indexing per-stage latency (total {ix['total_ms']} ms)")
    ax.set_ylabel("ms")
    for i, v in enumerate(t.values()):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "incremental_indexing_timeline.png", dpi=130); plt.close(fig)


def _knowledge_growth(plt, ix, figs):
    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ["child chunks\nindexed", "graph nodes\n(after add)"]
    vals = [ix["n_children"], ix["graph_nodes_added"]]
    ax.bar(labels, vals, color=[_C["kb"], _C["in"]])
    ax.set_title(f"Knowledge growth from 1 document (searchable: {ix['searchable']})")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "knowledge_growth.png", dpi=130); plt.close(fig)
