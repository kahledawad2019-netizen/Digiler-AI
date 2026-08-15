"""LinUCB — a contextual linear bandit (Li et al., 2010).

Per-arm ridge regression with an upper-confidence-bound exploration bonus. Given a
context vector it selects the arm with the highest optimistic value, and updates
that arm's statistics from the observed reward. State is serialisable so a policy
persists per learner. This is the online-policy core — no gradients, no LLM.
"""

from __future__ import annotations

import numpy as np


class LinUCB:
    def __init__(self, n_arms: int, dim: int, *, alpha: float = 0.6,
                 arms: list[str] | None = None) -> None:
        self.n_arms = n_arms
        self.dim = dim
        self.alpha = alpha
        self.arms = arms or [str(i) for i in range(n_arms)]
        self.A = [np.identity(dim) for _ in range(n_arms)]
        self.b = [np.zeros(dim) for _ in range(n_arms)]
        self.counts = [0] * n_arms

    # -- policy ---------------------------------------------------------- #
    def _value(self, x: np.ndarray, a: int, explore: bool) -> float:
        A_inv = np.linalg.inv(self.A[a])
        theta = A_inv @ self.b[a]
        mean = float(theta @ x)
        if not explore:
            return mean
        return mean + self.alpha * float(np.sqrt(max(0.0, x @ A_inv @ x)))

    def select(self, context, *, explore: bool = True) -> int:
        x = np.asarray(context, dtype=float)
        return int(np.argmax([self._value(x, a, explore) for a in range(self.n_arms)]))

    def update(self, arm: int, context, reward: float) -> None:
        x = np.asarray(context, dtype=float)
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x
        self.counts[arm] += 1

    # -- persistence ----------------------------------------------------- #
    def to_dict(self) -> dict:
        return {"n_arms": self.n_arms, "dim": self.dim, "alpha": self.alpha, "arms": self.arms,
                "A": [a.tolist() for a in self.A], "b": [b.tolist() for b in self.b],
                "counts": self.counts}

    @classmethod
    def from_dict(cls, d: dict) -> "LinUCB":
        bandit = cls(d["n_arms"], d["dim"], alpha=d.get("alpha", 0.6), arms=d.get("arms"))
        bandit.A = [np.asarray(a, dtype=float) for a in d["A"]]
        bandit.b = [np.asarray(b, dtype=float) for b in d["b"]]
        bandit.counts = d.get("counts", [0] * d["n_arms"])
        return bandit
