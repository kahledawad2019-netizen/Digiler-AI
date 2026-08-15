"""Study-Planner value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.core.enums import _StrEnum


class ActivityType(_StrEnum):
    READ = "read"
    WATCH = "watch"
    PRACTICE = "practice"
    QUIZ = "quiz"
    REVISION = "revision"


@dataclass
class StudyGoal:
    description: str = "master my weak concepts"
    concept_ids: list[str] = field(default_factory=list)   # explicit targets (else weak concepts)
    course: str | None = None                              # or a whole course
    deadline_days: int = 14
    minutes_per_day: int = 60


@dataclass
class StudyActivity:
    type: str
    concept: str
    concept_id: str
    minutes: int
    resource_id: str = ""
    title: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class StudyDay:
    day: int                                               # 1-based
    activities: list[StudyActivity] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        return sum(a.minutes for a in self.activities)

    def to_dict(self) -> dict:
        return {"day": self.day, "minutes": self.minutes,
                "activities": [a.to_dict() for a in self.activities]}


@dataclass
class StudyPlan:
    goal: str
    days: list[StudyDay] = field(default_factory=list)
    concepts: list[dict] = field(default_factory=list)     # {concept, mastery, priority}
    unscheduled: list[str] = field(default_factory=list)   # concepts that didn't fit
    stats: dict = field(default_factory=dict)

    @property
    def total_minutes(self) -> int:
        return sum(d.minutes for d in self.days)

    def to_dict(self) -> dict:
        return {"goal": self.goal, "days": [d.to_dict() for d in self.days],
                "concepts": self.concepts, "unscheduled": self.unscheduled,
                "total_minutes": self.total_minutes, "stats": self.stats}


@dataclass
class PlannerConfig:
    activity_minutes: dict = field(default_factory=lambda: {
        "read": 15, "watch": 12, "practice": 20, "quiz": 5, "revision": 10})
    revision_gap_days: int = 2
    weak_extra_practice: bool = True
    max_concepts: int = 40

    @classmethod
    def from_settings(cls, settings) -> "PlannerConfig":
        p = (getattr(settings, "planner", None) or {}) if settings else {}
        base = cls()
        am = dict(base.activity_minutes)
        am.update(p.get("activity_minutes", {}) or {})
        return cls(activity_minutes=am,
                   revision_gap_days=int(p.get("revision_gap_days", 2)),
                   weak_extra_practice=bool(p.get("weak_extra_practice", True)),
                   max_concepts=int(p.get("max_concepts", 40)))
