"""Stage 21 — RL figures (learning curves, contextual regret, difficulty mapping)."""

from __future__ import annotations

from pathlib import Path

_C = {"rl": "#55A868", "oracle": "#111827", "random": "#937860", "fixed-medium": "#4C72B0",
      "always-hard": "#C44E52", "always-easy": "#DD8452"}
_ORDER = ["oracle", "rl", "fixed-medium", "always-hard", "always-easy", "random"]


def render_all(payload: dict, figs: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    _curves(plt, payload, figs)
    _comparison(plt, payload, figs)
    _regret(plt, payload, figs)
    _mapping(plt, payload, figs)
    _training(plt, payload, figs)


def _curves(plt, p, figs):
    fig, ax = plt.subplots(figsize=(10, 6))
    for name, curve in p["trajectory_curves"].items():
        ax.plot(range(len(curve)), curve, label=name, color=_C.get(name, "#999"),
                lw=2.6 if name in ("rl", "oracle") else 1.6,
                ls="--" if name == "oracle" else "-")
    ax.axhline(0.7, color="#ccc", ls=":")
    ax.set_xlabel("interaction round"); ax.set_ylabel("learner mastery")
    ax.set_title("Learning trajectory — adaptive RL policy vs baselines"); ax.legend()
    ax.set_ylim(0, 1)
    fig.tight_layout(); fig.savefig(figs / "learning_curves.png", dpi=130); plt.close(fig)


def _comparison(plt, p, figs):
    tr = p["trajectory"]
    vals = [tr[n]["final_ability"] for n in _ORDER]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(_ORDER, vals, color=[_C.get(n, "#999") for n in _ORDER])
    ax.set_ylabel("final mastery"); ax.set_ylim(0, 1)
    ax.set_title("Final learning outcome by policy (single learner)")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout(); fig.savefig(figs / "policy_comparison.png", dpi=130); plt.close(fig)


def _regret(plt, p, figs):
    ctx = p["contextual"]
    vals = [ctx[n]["regret"] for n in _ORDER]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(_ORDER, vals, color=[_C.get(n, "#999") for n in _ORDER])
    ax.set_ylabel("mean regret vs oracle (lower = better)")
    ax.set_title("Contextual policy regret — learners at varying mastery")
    for i, v in enumerate(vals):
        ax.text(i, v, f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout(); fig.savefig(figs / "contextual_regret.png", dpi=130); plt.close(fig)


def _mapping(plt, p, figs):
    m = p["mapping"]
    xs = [r["theta"] for r in m]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(xs, [r["oracle"] for r in m], "s--", color=_C["oracle"], label="oracle (ZPD)", alpha=0.7)
    ax.step(xs, [r["rl"] for r in m], where="mid", color=_C["rl"], lw=2.5, label="RL policy")
    ax.set_xlabel("learner mastery (context)"); ax.set_ylabel("chosen difficulty")
    ax.set_title("Learned policy — difficulty adapts to mastery"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "difficulty_mapping.png", dpi=130); plt.close(fig)


def _training(plt, p, figs):
    curve = p["train_curve"]
    fig, ax = plt.subplots(figsize=(9, 5))
    xs = [i * (p["config"]["train_rounds"] / max(1, len(curve))) for i in range(len(curve))]
    ax.plot(xs, curve, color=_C["rl"], lw=2)
    ax.axhline(p["contextual"]["oracle"]["mean_reward"], color=_C["oracle"], ls="--",
               label=f"oracle mean reward {p['contextual']['oracle']['mean_reward']}")
    ax.set_xlabel("training round"); ax.set_ylabel("mean learning-reward (200-round window)")
    ax.set_title("RL online learning curve (converges toward the oracle)"); ax.legend()
    fig.tight_layout(); fig.savefig(figs / "training_curve.png", dpi=130); plt.close(fig)
