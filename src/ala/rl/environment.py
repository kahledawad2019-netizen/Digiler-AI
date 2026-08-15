"""SimulatedLearner — a synthetic student for **evaluating** the policy (test harness).

An IRT-style learner: each concept has a latent ability θ; the probability of a
correct answer to a question of difficulty d is σ(k·(θ−d)). Learning gain peaks in
the **zone of proximal development** (success probability ≈ 0.7) — too-easy or
too-hard questions teach little — so the optimal policy must *adapt* difficulty to
the learner's current ability. Ability grows with well-targeted practice and decays
slightly (forgetting). This is a standard RL simulator, clearly labelled: only the
learner is synthetic; the policy, reward and comparison are real.
"""

from __future__ import annotations

import math
import random


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


class SimulatedLearner:
    def __init__(self, abilities: dict[str, float], *, k: float = 6.0, learn_rate: float = 0.16,
                 forget: float = 0.004, seed: int = 0) -> None:
        self.ability = dict(abilities)                 # θ per concept in [0,1]
        self.k = k
        self.learn_rate = learn_rate
        self.forget = forget
        self.rng = random.Random(seed)

    def p_correct(self, concept_id: str, difficulty: float) -> float:
        return _sigmoid(self.k * (self.ability.get(concept_id, 0.3) - difficulty))

    def answer(self, concept_id: str, difficulty: float) -> tuple[bool, float, float]:
        theta = self.ability.get(concept_id, 0.3)
        p = self.p_correct(concept_id, difficulty)
        correct = self.rng.random() < p
        # learning gain peaks sharply in the ZPD (p≈0.6, productive struggle) and
        # vanishes for too-easy / too-hard questions → fixed difficulties plateau, so
        # the learner must be *challenged at the right level* to keep improving.
        zpd = math.exp(-((p - 0.6) ** 2) / (2 * 0.16 ** 2))
        gain = self.learn_rate * zpd * (1.0 - theta)
        self.ability[concept_id] = min(1.0, theta + gain)
        # response time: relatively harder question → slower (5–30 s)
        rel = difficulty - theta
        rt = 6.0 + 22.0 * _sigmoid(4.0 * rel) + self.rng.uniform(-1.5, 1.5)
        return correct, max(2.0, rt), gain

    def decay(self, active: set[str] | None = None) -> None:
        for cid in self.ability:
            if active and cid in active:
                continue
            self.ability[cid] = max(0.0, self.ability[cid] - self.forget)

    def mean_ability(self) -> float:
        return sum(self.ability.values()) / len(self.ability) if self.ability else 0.0
