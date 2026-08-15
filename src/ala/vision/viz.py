"""Stage 17 — Vision-RAG figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}
_KIND_C = {"figure": "#4C72B0", "table": "#DD8452", "diagram": "#8172B3",
           "chart": "#55A868", "screenshot": "#937860"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _pipeline(plt, figs)
    _kinds(plt, payload, figs)
    _retrieval(plt, payload, figs)
    _summary(plt, payload, figs)


def _pipeline(plt, figs):
    steps = ["Image /\nFigure", "Vision Encoder\n(CLIP)", "Caption\n(BLIP)", "OCR\n(tesseract)",
             "Structured\nmetadata", "IMAGE_CAPTION\nblock", "Embed +\nGraph", "Retriever /\nGraphRAG"]
    colors = [_C["grey"], _C["blue"], _C["orange"], _C["purple"], _C["purple"],
              _C["green"], _C["blue"], _C["green"]]
    fig, ax = plt.subplots(figsize=(15, 3))
    for i, (s, c) in enumerate(zip(steps, colors)):
        ax.add_patch(plt.Rectangle((i * 1.8, 0), 1.5, 1.3, color=c, alpha=0.9))
        ax.text(i * 1.8 + 0.75, 0.65, s, ha="center", va="center", color="white",
                fontsize=8, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i * 1.8 + 1.78, 0.65), xytext=(i * 1.8 + 1.5, 0.65),
                        arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(0, -0.45, "Images become text-carrying IMAGE_CAPTION blocks → same retriever, citations & GraphRAG.",
            fontsize=9, style="italic")
    ax.set_xlim(-0.2, len(steps) * 1.8); ax.set_ylim(-0.8, 1.5); ax.axis("off")
    ax.set_title("Vision RAG pipeline (Stage 17)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "vision_pipeline.png", dpi=130); plt.close(fig)


def _kinds(plt, p, figs):
    bk = p["by_kind"] or {"figure": 0}
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(list(bk.keys()), list(bk.values()), color=[_KIND_C.get(k, _C["grey"]) for k in bk])
    ax.set_title(f"Indexed image blocks by kind (n={p['n_image_chunks']}, from {p['n_figures']} figures)")
    ax.set_ylabel("count")
    for i, v in enumerate(bk.values()):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "figure_type_distribution.png", dpi=130); plt.close(fig)


def _retrieval(plt, p, figs):
    r = p["retrieval"]
    labels = ["Hit@1", "Hit@3", "MRR"]
    vals = [r["hit@1"], r["hit@3"], r["mrr"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, vals, color=[_C["green"], _C["blue"], _C["purple"]])
    ax.set_ylim(0, 1.08)
    ax.set_title(f"Figure retrieval — caption span → its figure (n={r['n']})")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "retrieval_quality.png", dpi=130); plt.close(fig)


def _summary(plt, p, figs):
    labels = ["resources\nscanned", "with\nfigures", "figures\nextracted", "image\nchunks"]
    vals = [p["source_resources_scanned"], p["resources_with_figures"],
            p["n_figures"], p["n_image_chunks"]]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, vals, color=[_C["grey"], _C["blue"], _C["orange"], _C["green"]])
    ax.set_title("Vision indexing coverage (real corpus)")
    for i, v in enumerate(vals):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "ingest_timeline.png", dpi=130); plt.close(fig)
