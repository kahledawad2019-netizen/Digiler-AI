"""Stage 22 — AI-Agents figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _architecture(plt, figs)
    _routing(plt, payload, figs)
    _quiz_eval(plt, payload, figs)
    _latency(plt, payload, figs)


def _architecture(plt, figs):
    import numpy as np
    agents = ["Tutor", "Quiz", "Evaluator", "Planner", "Research", "WebResearch", "Curator"]
    services = ["GraphRAG", "Student Model", "RL Policy", "Planner", "Research Mode", "Ingestor"]
    fig, ax = plt.subplots(figsize=(13, 7))
    ax.add_patch(plt.Circle((0, 0), 0.6, color=_C["purple"], alpha=0.9))
    ax.text(0, 0, "Coordinator", ha="center", va="center", color="white", fontweight="bold")
    for i, a in enumerate(agents):
        ang = 2 * np.pi * i / len(agents) + np.pi / 2
        x, y = 2.6 * np.cos(ang), 2.6 * np.sin(ang)
        ax.add_patch(plt.Rectangle((x - 0.65, y - 0.28), 1.3, 0.56, color=_C["green"], alpha=0.9))
        ax.text(x, y, a, ha="center", va="center", color="white", fontsize=9, fontweight="bold")
        ax.plot([0.5 * np.cos(ang), x - 0.6 * np.cos(ang)], [0.5 * np.sin(ang), y - 0.3 * np.sin(ang)],
                color="#bbb", lw=1, zorder=0)
    for j, s in enumerate(services):
        x = -5.0 + 0 * j
        y = 2.2 - j * 0.9
        ax.add_patch(plt.Rectangle((x - 0.9, y - 0.3), 1.8, 0.6, color=_C["blue"], alpha=0.9))
        ax.text(x, y, s, ha="center", va="center", color="white", fontsize=8)
    ax.text(-5.0, 3.0, "shared services\n(single source of truth)", ha="center", fontsize=9, style="italic")
    ax.annotate("", xy=(-4.0, 0.0), xytext=(-0.7, 0.0), arrowprops=dict(arrowstyle="<->", lw=1.4))
    ax.text(-2.4, 0.25, "tools reuse\n(one retrieval path)", ha="center", fontsize=8, style="italic")
    ax.set_xlim(-6.2, 3.6); ax.set_ylim(-3.4, 3.4); ax.axis("off")
    ax.set_title("AI Agents — roles over shared services (Stage 22)", fontsize=13)
    fig.tight_layout(); fig.savefig(figs / "architecture.png", dpi=130); plt.close(fig)


def _routing(plt, p, figs):
    from collections import Counter
    detail = p["routing"]["detail"]
    ok = Counter(d["routed"] for d in detail if d["routed"] == d["expected"])
    bad = Counter(d["routed"] for d in detail if d["routed"] != d["expected"])
    roles = sorted({d["expected"] for d in detail} | set(ok) | set(bad))
    import numpy as np
    x = np.arange(len(roles))
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(x, [ok.get(r, 0) for r in roles], color=_C["green"], label="correct")
    ax.bar(x, [bad.get(r, 0) for r in roles], bottom=[ok.get(r, 0) for r in roles],
           color=_C["red"], label="misrouted")
    ax.set_xticks(x); ax.set_xticklabels(roles, rotation=20, ha="right")
    ax.set_title(f"Coordinator routing (accuracy {p['routing']['accuracy']})")
    ax.set_ylabel("requests"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "routing_accuracy.png", dpi=130); plt.close(fig)


def _quiz_eval(plt, p, figs):
    qe = p["quiz_eval"]
    labels = ["good-answer\naccuracy", "bad-answer\nrejection", "discrimination"]
    vals = [qe["good_answer_accuracy"], qe["bad_answer_rejection"], qe["discrimination"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, vals, color=[_C["green"], _C["blue"], _C["purple"]])
    ax.set_ylim(0, 1.08); ax.set_title(f"Quiz → Evaluator grading ({qe['n_concepts']} concepts)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "quiz_evaluation.png", dpi=130); plt.close(fig)


def _latency(plt, p, figs):
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(["Tutor (GraphRAG)"], [p["tutor"]["mean_latency_ms"]], color=_C["blue"])
    ax.set_title("Agent latency"); ax.set_ylabel("ms / request")
    ax.text(0, p["tutor"]["mean_latency_ms"], f"{p['tutor']['mean_latency_ms']:.0f}",
            ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "agent_latency.png", dpi=130); plt.close(fig)
