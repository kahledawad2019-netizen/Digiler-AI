"""Stage 19 — presentation-quality dashboard figures (PNG), from real learner data."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}


def _mcolor(v):
    return _C["red"] if v < 0.4 else (_C["orange"] if v < 0.7 else _C["green"])


def render_all(data, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = data.to_dict() if hasattr(data, "to_dict") else data
    _domain(plt, d, figs)
    _heatmap(plt, d, figs)
    _confidence(plt, d, figs)
    _completion_time(plt, d, figs)
    _recommendations(plt, d, figs)


def _domain(plt, d, figs):
    dm = d["domain_mastery"]
    fig, ax = plt.subplots(figsize=(9, 5))
    labels = [x["domain"] for x in dm][::-1]
    vals = [x["mastery"] for x in dm][::-1]
    ax.barh(labels, vals, color=[_mcolor(v) for v in vals])
    ax.set_xlim(0, 1); ax.set_title("Knowledge mastery by domain")
    for i, v in enumerate(vals):
        ax.text(v, i, f" {v:.2f}", va="center", fontsize=9)
    fig.tight_layout(); fig.savefig(figs / "mastery_by_domain.png", dpi=130); plt.close(fig)


def _heatmap(plt, d, figs):
    import numpy as np
    cells = d["heatmap"]
    if not cells:
        return
    cols = 12
    rows = (len(cells) + cols - 1) // cols
    grid = np.full((rows, cols), np.nan)
    for i, c in enumerate(cells):
        grid[i // cols, i % cols] = c["mastery"]
    fig, ax = plt.subplots(figsize=(10, max(2.2, rows * 0.5)))
    im = ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Weak-concept heatmap (red = weak, green = mastered)")
    fig.colorbar(im, ax=ax, shrink=0.7, label="mastery")
    fig.tight_layout(); fig.savefig(figs / "mastery_heatmap.png", dpi=130); plt.close(fig)


def _confidence(plt, d, figs):
    conf = d["confidence_evolution"]
    fig, ax = plt.subplots(figsize=(9, 5))
    if conf:
        xs = list(range(1, len(conf) + 1))
        ax.plot(xs, [c["score"] for c in conf], "o", color=_C["grey"], alpha=0.5, label="score")
        ax.plot(xs, [c["avg"] for c in conf], "-", color=_C["blue"], lw=2, label="running avg")
        ax.axhline(0.5, color="#bbb", ls="--")
        ax.legend()
    ax.set_ylim(0, 1.05); ax.set_xlabel("assessment #"); ax.set_ylabel("score")
    ax.set_title("Confidence evolution")
    fig.tight_layout(); fig.savefig(figs / "confidence_evolution.png", dpi=130); plt.close(fig)


def _completion_time(plt, d, figs):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    ts = d["time_spent"]["by_type"]
    a1.bar(list(ts.keys()), list(ts.values()), color=_C["purple"])
    a1.set_title(f"Estimated time spent ({d['time_spent']['total_minutes']:.0f} min total)")
    a1.set_ylabel("minutes")
    courses = d["completion"].get("by_course", [])
    if courses:
        a2.barh([c["course"] for c in courses][::-1], [c["rate"] for c in courses][::-1],
                color=_C["green"])
        a2.set_xlim(0, 1); a2.set_title("Completion rate by course")
    else:
        cov = d["completion"].get("concept_coverage", 0)
        a2.bar(["concept\ncoverage"], [cov], color=_C["green"]); a2.set_ylim(0, 1)
        a2.set_title("Concept coverage")
    fig.tight_layout(); fig.savefig(figs / "completion_and_time.png", dpi=130); plt.close(fig)


def _recommendations(plt, d, figs):
    recs = d["recommendations"][:8]
    fig, ax = plt.subplots(figsize=(10, max(2.5, len(recs) * 0.55)))
    kc = {"review": _C["orange"], "practice": _C["red"], "explore": _C["blue"]}
    for i, r in enumerate(recs[::-1]):
        ax.barh(i, 1, color=kc.get(r["kind"], _C["grey"]), alpha=0.25)
        ax.text(0.01, i, f'{r["kind"].upper()}: {r["concept"][:40]}  —  {r["reason"]}',
                va="center", fontsize=9)
    ax.set_xlim(0, 1); ax.set_yticks([]); ax.set_xticks([])
    ax.set_title("Study recommendations")
    fig.tight_layout(); fig.savefig(figs / "recommendations.png", dpi=130); plt.close(fig)
