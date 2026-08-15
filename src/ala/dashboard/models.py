"""Dashboard value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Recommendation:
    kind: str                    # review | prerequisite | practice | explore
    concept: str
    concept_id: str
    reason: str
    mastery: float = 0.0
    resources: list[dict] = field(default_factory=list)   # {resource_id, title}

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DashboardData:
    student_id: str
    profile: dict = field(default_factory=dict)
    summary: dict = field(default_factory=dict)             # overall mastery, n_weak/strong…
    mastery_distribution: dict = field(default_factory=dict)
    heatmap: list[dict] = field(default_factory=list)       # [{concept, domain, mastery}]
    domain_mastery: list[dict] = field(default_factory=list)  # [{domain, mastery, n}]
    weak_concepts: list[dict] = field(default_factory=list)
    strong_concepts: list[dict] = field(default_factory=list)
    timeline: list[dict] = field(default_factory=list)
    progress: dict = field(default_factory=dict)            # counts by event type
    time_spent: dict = field(default_factory=dict)          # minutes by type + total
    completion: dict = field(default_factory=dict)
    confidence_evolution: list[dict] = field(default_factory=list)   # [{t, score, avg}]
    recommendations: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


@dataclass
class DashboardConfig:
    typical_minutes: dict = field(default_factory=lambda: {
        "quiz": 3, "exam": 45, "lesson": 15, "video": 10, "reading": 8, "interaction": 2})
    recommend_k: int = 6

    @classmethod
    def from_settings(cls, settings) -> "DashboardConfig":
        d = (getattr(settings, "dashboard", None) or {}) if settings else {}
        base = cls()
        tm = dict(base.typical_minutes)
        tm.update(d.get("typical_minutes", {}) or {})
        return cls(typical_minutes=tm, recommend_k=int(d.get("recommend_k", 6)))
