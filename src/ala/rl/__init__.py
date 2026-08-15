"""Stage 21 — RL Adaptive Learning.

A contextual-bandit online-policy layer (NOT LLM training). It observes the
learner's state (concept mastery, recent accuracy, response time) and adapts
**quiz difficulty**, **explanation style** and **question type** to maximise
learning gain, with reward shaping (correct / fast / mastery-gain / retention;
penalties for repeated mistakes, forgetting, skipped prerequisites). Integrates
with the Student Model (Stage 18); every update advances mastery. Fully additive.
"""

from ala.rl.bandit import LinUCB
from ala.rl.controller import AdaptiveController
from ala.rl.models import Interaction, RLConfig
from ala.rl.reward import RewardModel

__all__ = ["AdaptiveController", "LinUCB", "RewardModel", "RLConfig", "Interaction"]
