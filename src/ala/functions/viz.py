"""Stage 23 — Function-Calling figures, from real benchmark output."""

from __future__ import annotations

from pathlib import Path

_C = {"blue": "#4C72B0", "green": "#55A868", "orange": "#DD8452", "purple": "#8172B3",
      "grey": "#937860", "red": "#C44E52"}


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _catalog(plt, payload, figs)
    _safety(plt, payload, figs)
    _latency(plt, payload, figs)


def _catalog(plt, p, figs):
    safe = {"calculator", "python", "search", "planner", "quiz", "web_search", "pdf",
            "video", "calendar"}
    fns = p["functions"]
    colors = [_C["red"] if f == "knowledge_update" else _C["green"] for f in fns]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(range(len(fns)), [1] * len(fns), color=colors)
    ax.set_xticks(range(len(fns))); ax.set_xticklabels(fns, rotation=30, ha="right")
    ax.set_yticks([]); ax.set_title(f"Function-calling catalog ({p['n_functions']} tools)")
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(color=_C["green"], label="safe / read-only"),
                       mp.Patch(color=_C["red"], label="mutating (gated)")], loc="upper right")
    fig.tight_layout(); fig.savefig(figs / "tool_catalog.png", dpi=130); plt.close(fig)


def _safety(plt, p, figs):
    sf, vd, val = p["safety"], p["valid_dispatch"], p["validation"]
    labels = ["attacks\nblocked", "valid calls\nsucceeded", "malformed\nrejected"]
    vals = [sf["blocked_rate"], vd["success_rate"], val["rejection_rate"]]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar(labels, vals, color=[_C["red"], _C["green"], _C["orange"]])
    ax.set_ylim(0, 1.08)
    ax.set_title("Function-calling safety & correctness")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.2f}", ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "safety.png", dpi=130); plt.close(fig)


def _latency(plt, p, figs):
    lat = p["latency_ms"]
    items = sorted(lat.items(), key=lambda kv: kv[1], reverse=True)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh([k for k, _ in items][::-1], [v for _, v in items][::-1], color=_C["blue"])
    ax.set_xlabel("ms"); ax.set_title("Tool dispatch latency")
    fig.tight_layout(); fig.savefig(figs / "dispatch_latency.png", dpi=130); plt.close(fig)
