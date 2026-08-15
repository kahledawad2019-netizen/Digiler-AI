"""Stage 12 — presentation-quality GraphRAG figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "red": "#C44E52", "grey": "#937860"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    m = payload["metrics"]
    ex = payload["example"]
    _pipeline_diagram(plt, figs)
    _grounding(plt, m, figs)
    _context_precision_recall(plt, m, figs)
    _citation_sources(plt, m, figs)
    _token_distribution(plt, payload.get("tokens", []), m, figs)
    _context_composition(plt, ex, figs)
    _evidence_contribution(plt, ex, figs)
    _reasoning_flow(plt, ex, figs)


def _pipeline_diagram(plt, figs):
    steps = ["User\nQuestion", "Hybrid\nRetriever", "Graph\nRetriever", "Evidence\nMerger",
             "Context\nBuilder", "Prompt\nBuilder", "LLM /\nGrounded Gen", "Cited\nAnswer"]
    colors = [_C["grey"], _C["blue"], _C["green"], _C["orange"], _C["purple"],
              _C["purple"], _C["red"], _C["green"]]
    fig, ax = plt.subplots(figsize=(15, 3.2))
    for i, (s, c) in enumerate(zip(steps, colors)):
        ax.add_patch(plt.Rectangle((i * 1.85, 0), 1.5, 1.4, color=c, alpha=0.9))
        ax.text(i * 1.85 + 0.75, 0.7, s, ha="center", va="center", color="white",
                fontsize=9, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i * 1.85 + 1.8, 0.7), xytext=(i * 1.85 + 1.5, 0.7),
                        arrowprops=dict(arrowstyle="->", lw=1.6))
    ax.text(0, -0.4, "The LLM receives ONLY the structured prompt built from the Evidence Package — never raw retrieval output.",
            fontsize=9, style="italic")
    ax.set_xlim(-0.2, len(steps) * 1.85); ax.set_ylim(-0.8, 1.6); ax.axis("off")
    ax.set_title("GraphRAG pipeline (Stage 12)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "pipeline_diagram.png", dpi=130); plt.close(fig)


def _grounding(plt, m, figs):
    labels = ["grounding\nratio", "citation\nvalidity", "answer has\ncitation", "graph\ncoverage"]
    vals = [m["grounding_ratio"], m["citation_validity"], m["answer_has_citation"], m["graph_coverage"]]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, vals, color=[_C["green"], _C["green"], _C["blue"], _C["purple"]])
    ax.set_ylim(0, 1.08); ax.set_title("GraphRAG grounding & citation integrity (real corpus)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "grounding.png", dpi=130); plt.close(fig)


def _context_precision_recall(plt, m, figs):
    labels = ["context\nprecision", "context\nrecall", "multi-hop\npresence"]
    vals = [m["context_precision"], m["context_recall"], m["multi_hop_presence"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, vals, color=[_C["orange"], _C["blue"], _C["purple"]])
    ax.set_ylim(0, 1.08); ax.set_title("Context precision / recall / multi-hop (real corpus)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "context_precision_recall.png", dpi=130); plt.close(fig)


def _citation_sources(plt, m, figs):
    st = m.get("citation_source_types") or {"document": 1}
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(list(st.keys()), list(st.values()),
           color=[_C["blue"], _C["orange"], _C["green"], _C["purple"], _C["grey"]][:len(st)])
    ax.set_title("Citation sources by type (across benchmark)")
    ax.set_ylabel("citations")
    for i, v in enumerate(st.values()):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "citation_sources.png", dpi=130); plt.close(fig)


def _token_distribution(plt, tokens, m, figs):
    fig, ax = plt.subplots(figsize=(8, 5))
    if tokens:
        ax.hist(tokens, bins=15, color=_C["blue"], alpha=0.85)
        ax.axvline(m["avg_context_tokens"], color=_C["red"], linestyle="--",
                   label=f"mean {m['avg_context_tokens']:.0f}")
        ax.legend()
    ax.set_title("Context size distribution (compression under token budget)")
    ax.set_xlabel("context tokens"); ax.set_ylabel("questions")
    fig.tight_layout(); fig.savefig(figs / "token_distribution.png", dpi=130); plt.close(fig)


def _context_composition(plt, ex, figs):
    c = ex["context"]
    labels = ["sources", "concepts", "relations", "prerequisites"]
    vals = [len(c["sources"]), len(c["concepts"]), len(c["relations"]), len(c["prerequisites"])]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, vals, color=[_C["blue"], _C["green"], _C["orange"], _C["purple"]])
    ax.set_title(f'Reasoning-context composition — "{ex["question"]}"')
    ax.set_ylabel("elements")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "context_composition.png", dpi=130); plt.close(fig)


def _evidence_contribution(plt, ex, figs):
    src = ex["context"]["sources"]
    if not src:
        return
    labels = [f'{s["cid"]}\n{s["resource_id"][-12:]}' for s in src]
    conf = [s["confidence"] for s in src]
    toks = [s["tokens"] for s in src]
    import numpy as np
    x = np.arange(len(src))
    fig, ax1 = plt.subplots(figsize=(9, 5))
    ax1.bar(x - 0.2, conf, 0.4, label="confidence", color=_C["green"])
    ax1.set_ylabel("confidence"); ax1.set_ylim(0, 1.05)
    ax2 = ax1.twinx()
    ax2.bar(x + 0.2, toks, 0.4, label="tokens", color=_C["blue"])
    ax2.set_ylabel("tokens")
    ax1.set_xticks(x); ax1.set_xticklabels(labels)
    ax1.set_title(f'Evidence contribution per source — "{ex["question"]}"')
    fig.legend(loc="upper right")
    fig.tight_layout(); fig.savefig(figs / "evidence_contribution.png", dpi=130); plt.close(fig)


def _reasoning_flow(plt, ex, figs):
    trace = ex["reasoning_trace"]
    fig, ax = plt.subplots(figsize=(11, 5.5))
    n = len(trace)
    for i, step in enumerate(trace):
        y = n - i
        ax.add_patch(plt.Rectangle((0, y - 0.35), 10, 0.7, color=_C["purple"], alpha=0.15))
        ax.text(0.15, y, f"{i+1}. {step}", va="center", fontsize=9)
        if i < n - 1:
            ax.annotate("", xy=(0.4, y - 0.65), xytext=(0.4, y - 0.35),
                        arrowprops=dict(arrowstyle="->", lw=1.4))
    ax.set_xlim(0, 10); ax.set_ylim(0, n + 1); ax.axis("off")
    ax.set_title(f'Reasoning trace — "{ex["question"]}"', fontsize=12)
    fig.tight_layout(); fig.savefig(figs / "reasoning_flow.png", dpi=130); plt.close(fig)
