"""Stage 18 — Student-Model figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _pipeline(plt, figs)
    _distribution(plt, payload, figs)
    _weak_strong(plt, payload, figs)
    _curve(plt, payload, figs)
    _personalization(plt, payload, figs)


def _pipeline(plt, figs):
    steps = ["Learning\nevents", "Mastery\nmodel", "Concept\nmastery", "Weak / Strong\nconcepts",
             "Personalized\nRetriever", "GraphRAG\nanswer", "Analytics"]
    colors = [_C["grey"], _C["purple"], _C["blue"], _C["orange"], _C["green"], _C["blue"], _C["purple"]]
    fig, ax = plt.subplots(figsize=(14, 3))
    for i, (s, c) in enumerate(zip(steps, colors)):
        ax.add_patch(plt.Rectangle((i * 1.9, 0), 1.55, 1.3, color=c, alpha=0.9))
        ax.text(i * 1.9 + 0.77, 0.65, s, ha="center", va="center", color="white",
                fontsize=8.5, fontweight="bold")
        if i < len(steps) - 1:
            ax.annotate("", xy=(i * 1.9 + 1.88, 0.65), xytext=(i * 1.9 + 1.55, 0.65),
                        arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.text(0, -0.45, "Learner profile is stored SEPARATELY from the KB; mastery is keyed to concept-graph ids.",
            fontsize=9, style="italic")
    ax.set_xlim(-0.2, len(steps) * 1.9); ax.set_ylim(-0.8, 1.5); ax.axis("off")
    ax.set_title("Student Model (Stage 18)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "student_pipeline.png", dpi=130); plt.close(fig)


def _distribution(plt, p, figs):
    h = p["analytics"]["mastery_histogram"]
    colors = [_C["red"], _C["orange"], _C["grey"], _C["blue"], _C["green"]]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(h["bins"], h["counts"], color=colors[:len(h["bins"])])
    ax.set_title("Concept-mastery distribution"); ax.set_xlabel("mastery"); ax.set_ylabel("concepts")
    for i, v in enumerate(h["counts"]):
        ax.text(i, v, str(v), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "mastery_distribution.png", dpi=130); plt.close(fig)


def _weak_strong(plt, p, figs):
    weak = p["analytics"]["weak_concepts"][:6][::-1]
    strong = p["analytics"]["strong_concepts"][:6][::-1]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.barh([w["concept"][:22] for w in weak], [w["mastery"] for w in weak], color=_C["red"])
    a1.set_title("Weak concepts (need review)"); a1.set_xlim(0, 1)
    a2.barh([s["concept"][:22] for s in strong], [s["mastery"] for s in strong], color=_C["green"])
    a2.set_title("Strong concepts (mastered)"); a2.set_xlim(0, 1)
    fig.tight_layout(); fig.savefig(figs / "weak_strong_concepts.png", dpi=130); plt.close(fig)


def _curve(plt, p, figs):
    c = p["learning_curve"]
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = list(range(len(c["mastery"])))
    ax.plot(xs, c["mastery"], "o-", color=_C["purple"], lw=2, label="mastery")
    for i, o in enumerate(c["outcomes"], start=1):
        ax.scatter(i, c["mastery"][i], color=_C["green"] if o else _C["red"], zorder=5, s=80)
    ax.axhline(0.4, color=_C["grey"], ls="--", alpha=0.6); ax.axhline(0.7, color=_C["grey"], ls="--", alpha=0.6)
    ax.set_ylim(0, 1); ax.set_xlabel("quiz attempt"); ax.set_ylabel("mastery")
    ax.set_title("Learning curve (green = correct, red = incorrect)"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "learning_curve.png", dpi=130); plt.close(fig)


def _personalization(plt, p, figs):
    pe = p["personalization"]
    fig, ax = plt.subplots(figsize=(7, 5))
    vals = [pe["base_weak_coverage@10"], pe["personalized_weak_coverage@10"]]
    ax.bar(["base\nhybrid", "personalized"], vals, color=[_C["grey"], _C["green"]])
    ax.set_title(f"Weak-concept coverage@10 (lift {pe['lift']:+})")
    ax.set_ylabel("fraction of top-10 teaching a weak concept")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "personalization_effect.png", dpi=130); plt.close(fig)
