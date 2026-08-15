"""RewardModel — shape the learning reward from an interaction outcome.

Positive: correctness + **mastery gain** (the true learning signal) + speed.
Negative: repeated mistakes, forgetting, skipped prerequisites. The policy that
maximises this reward is the one that maximises learning — not just correctness,
so it favours the zone of proximal development over trivially easy questions.
"""

from __future__ import annotations

from ala.rl.models import RLConfig


class RewardModel:
    def __init__(self, config: RLConfig | None = None, *, max_time: float = 30.0) -> None:
        self.config = config or RLConfig()
        self.max_time = max_time

    def compute(self, *, correct: bool, mastery_gain: float, response_time: float = 0.0,
                repeat_mistake: bool = False, skipped_prerequisite: bool = False,
                forgetting: float = 0.0) -> float:
        w = self.config.reward
        r = w["correct"] * (1.0 if correct else 0.0)
        r += w["mastery_gain"] * mastery_gain
        r -= w["time_penalty"] * min(1.0, response_time / self.max_time)
        if repeat_mistake:
            r -= w["repeat_mistake"]
        if skipped_prerequisite:
            r -= w["skip_prerequisite"]
        r -= w.get("mastery_gain", 1.0) * max(0.0, forgetting)     # forgetting hurts
        return round(r, 5)
