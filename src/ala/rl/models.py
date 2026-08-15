"""RL value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Interaction:
    """One adaptive step: context → action → outcome → reward."""
    concept_id: str
    context: list[float]
    decision: str                 # difficulty | explanation_style | question_type
    action: str                   # the chosen arm (label)
    action_index: int
    correct: bool | None = None
    response_time: float = 0.0    # seconds
    mastery_before: float = 0.0
    mastery_after: float = 0.0
    reward: float = 0.0

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RLConfig:
    alpha: float = 0.6
    difficulties: list[float] = field(default_factory=lambda: [0.2, 0.35, 0.5, 0.65, 0.8])
    difficulty_labels: list[str] = field(default_factory=lambda: [
        "very-easy", "easy", "medium", "hard", "very-hard"])
    explanation_styles: list[str] = field(default_factory=lambda: [
        "concise", "balanced", "detailed", "example-driven"])
    question_types: list[str] = field(default_factory=lambda: [
        "recall", "application", "conceptual"])
    location: str = "data/rl"
    reward: dict = field(default_factory=lambda: {
        "correct": 0.4, "mastery_gain": 1.0, "time_penalty": 0.15,
        "repeat_mistake": 0.3, "skip_prerequisite": 0.3})

    @classmethod
    def from_settings(cls, settings) -> "RLConfig":
        r = (getattr(settings, "rl", None) or {}) if settings else {}
        base = cls()
        rw = dict(base.reward)
        rw.update(r.get("reward", {}) or {})
        return cls(
            alpha=float(r.get("alpha", 0.6)),
            difficulties=list(r.get("difficulties", base.difficulties)),
            explanation_styles=list(r.get("explanation_styles", base.explanation_styles)),
            question_types=list(r.get("question_types", base.question_types)),
            location=str(r.get("location", "data/rl")),
            reward=rw,
        )
