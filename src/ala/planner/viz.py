"""Stage 20 — Study-Planner figures (visual timeline), from a real plan."""

from __future__ import annotations

from pathlib import Path

_ACT_C = {"read": "#4C72B0", "watch": "#DD8452", "practice": "#C44E52",
          "quiz": "#8172B3", "revision": "#55A868"}


def render_all(plan, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    d = plan.to_dict() if hasattr(plan, "to_dict") else plan
    _timeline(plt, d, figs)
    _allocation(plt, d, figs)
    _daily_load(plt, d, figs)


def _timeline(plt, d, figs):
    days = d["days"]
    fig, ax = plt.subplots(figsize=(12, max(3, len(days) * 0.5)))
    for row, day in enumerate(days):
        left = 0
        for a in day["activities"]:
            ax.barh(row, a["minutes"], left=left, height=0.6,
                    color=_ACT_C.get(a["type"], "#999"), edgecolor="white")
            if a["minutes"] >= 12:
                ax.text(left + a["minutes"] / 2, row, a["type"][0].upper(),
                        ha="center", va="center", color="white", fontsize=8)
            left += a["minutes"]
    ax.set_yticks(range(len(days)))
    ax.set_yticklabels([f"Day {day['day']}" for day in days])
    ax.invert_yaxis(); ax.set_xlabel("minutes")
    ax.set_title(f"Study plan timeline — {d['goal']}")
    import matplotlib.patches as mp
    ax.legend(handles=[mp.Patch(color=c, label=k) for k, c in _ACT_C.items()],
              loc="lower right", ncol=5, fontsize=8)
    fig.tight_layout(); fig.savefig(figs / "study_timeline.png", dpi=130); plt.close(fig)


def _allocation(plt, d, figs):
    from collections import Counter
    mins: Counter = Counter()
    for day in d["days"]:
        for a in day["activities"]:
            mins[a["type"]] += a["minutes"]
    fig, ax = plt.subplots(figsize=(7, 5))
    keys = list(mins.keys())
    ax.bar(keys, [mins[k] for k in keys], color=[_ACT_C.get(k, "#999") for k in keys])
    ax.set_title("Time allocation by activity"); ax.set_ylabel("minutes")
    for i, k in enumerate(keys):
        ax.text(i, mins[k], str(mins[k]), ha="center", va="bottom")
    fig.tight_layout(); fig.savefig(figs / "time_allocation.png", dpi=130); plt.close(fig)


def _daily_load(plt, d, figs):
    days = d["days"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    mins = [day["minutes"] for day in days]
    ax.bar([f"D{day['day']}" for day in days], mins, color="#4C72B0")
    cap = d["stats"].get("minutes_per_day")
    if cap:
        ax.axhline(cap, color="#C44E52", ls="--", label=f"daily budget {cap} min")
        ax.legend()
    ax.set_title("Daily study load"); ax.set_ylabel("minutes")
    fig.tight_layout(); fig.savefig(figs / "daily_load.png", dpi=130); plt.close(fig)
