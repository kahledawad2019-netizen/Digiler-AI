"""Reinforcement Learning — expose the live LinUCB contextual-bandit policy state.

Read-only view of the adaptive difficulty policy for the current learner: the context
(state), each difficulty arm's exploitation estimate + exploration bonus + UCB value +
pull count, the chosen arm, and whether the policy is currently exploring or exploiting.
Everything is the real bandit state (no mock).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/rl", tags=["rl"])


@router.get("/status")
async def rl_status(concept: str | None = None,
                    services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    def _run():
        import numpy as np
        from ala.graph.models import NodeType

        rl = services.rl                       # AdaptiveController
        sm = services.student_model

        cid = concept
        if not cid:
            weak = sm.weak_concepts(user.student_id, k=1)
            if weak:
                cid = weak[0].concept_id
            else:
                cid = next((n for n in services.graph.nodes(NodeType.CONCEPT.value)), None)
        if not cid:
            return {"available": False, "reason": "no concepts in the graph"}

        x = rl.context(user.student_id, cid)   # [mastery, recent_acc, exposure, bias]
        bandits = rl._bandits(user.student_id)
        bandit = bandits["difficulty"]
        difficulties = rl.config.difficulties
        xa = np.asarray(x, dtype=float)

        arms = []
        for a in range(bandit.n_arms):
            A_inv = np.linalg.inv(bandit.A[a])
            theta = A_inv @ bandit.b[a]
            mean = float(theta @ xa)                                   # exploitation
            bonus = bandit.alpha * float(np.sqrt(max(0.0, xa @ A_inv @ xa)))  # exploration
            arms.append({"arm": a, "difficulty": difficulties[a],
                         "exploitation": round(mean, 4), "exploration_bonus": round(bonus, 4),
                         "ucb": round(mean + bonus, 4), "count": int(bandit.counts[a])})
        chosen = max(range(len(arms)), key=lambda i: arms[i]["ucb"])
        c = arms[chosen]
        strategy = "exploring (uncertainty-driven)" if c["exploration_bonus"] >= abs(c["exploitation"]) \
            else "exploiting (value-driven)"

        return {
            "available": True,
            "algorithm": "LinUCB (contextual linear bandit)",
            "concept": cid.replace("concept:", ""),
            "alpha": bandit.alpha,
            "context": {"mastery": round(x[0], 4), "recent_accuracy": round(x[1], 4),
                        "exposure": round(x[2], 4)},
            "arms": arms,
            "chosen_arm": chosen,
            "chosen_difficulty": difficulties[chosen],
            "total_interactions": int(sum(bandit.counts)),
            "strategy": strategy,
            "decisions": list(bandits.keys()),
        }
    return await run_in_threadpool(_run)
