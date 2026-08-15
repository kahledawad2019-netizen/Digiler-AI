"""Evidence-package visualizations (presentation-quality PNGs).

- ``pipeline_diagram``: Question → Retrieved Chunks → Evidence Package →
  LLM Context → Grounded Answer.
- ``evidence_breakdown``: per-item confidence + semantic similarity + fused score.
"""

from __future__ import annotations

from pathlib import Path


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def pipeline_diagram(path: Path, title: str = "Evidence Package pipeline") -> Path:
    plt = _plt()
    from matplotlib.patches import FancyBboxPatch

    stages = ["Question", "Hybrid Retrieval\n(dense + BM25 + RRF)", "Evidence Package\n(cited, scored, validated)",
              "LLM Context\n(grounded prompt)", "Grounded Answer\n(with citations)"]
    colors = ["#4C72B0", "#DD8452", "#55A868", "#8172B3", "#C44E52"]
    fig, ax = plt.subplots(figsize=(13, 3))
    ax.set_xlim(0, len(stages)); ax.set_ylim(0, 1); ax.axis("off")
    for i, (label, c) in enumerate(zip(stages, colors)):
        ax.add_patch(FancyBboxPatch((i + 0.06, 0.28), 0.82, 0.44,
                                    boxstyle="round,pad=0.02", linewidth=0, facecolor=c, alpha=0.85))
        ax.text(i + 0.47, 0.5, label, ha="center", va="center", color="white",
                fontsize=10, fontweight="bold")
        if i < len(stages) - 1:
            ax.annotate("", xy=(i + 1.05, 0.5), xytext=(i + 0.9, 0.5),
                        arrowprops=dict(arrowstyle="-|>", color="#333", lw=2))
    ax.set_title(title, fontsize=13)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140); plt.close(fig)
    return Path(path)


def evidence_breakdown(package, path: Path) -> Path:
    plt = _plt()
    import numpy as np

    items = package.items
    x = np.arange(len(items))
    conf = [it.confidence for it in items]
    sem = [it.semantic_similarity or 0.0 for it in items]
    fused = [it.fused_score for it in items]
    fmax = max(fused) or 1.0
    fused_n = [f / fmax for f in fused]

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.bar(x - 0.25, conf, 0.25, label="confidence", color="#55A868")
    ax.bar(x, sem, 0.25, label="semantic similarity (dense cos)", color="#4C72B0")
    ax.bar(x + 0.25, fused_n, 0.25, label="fused score (norm.)", color="#DD8452")
    ax.set_xticks(x)
    ax.set_xticklabels([f"[{i+1}]\n{it.source_type}" for i, it in enumerate(items)], fontsize=8)
    ax.set_ylim(0, 1); ax.set_ylabel("score")
    ax.set_title(f'Evidence breakdown — "{package.query[:60]}"  (overall conf {package.overall_confidence})')
    ax.legend(); fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=130); plt.close(fig)
    return Path(path)
