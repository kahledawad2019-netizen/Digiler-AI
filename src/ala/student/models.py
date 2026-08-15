"""Student-Model value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.core.clock import utcnow_iso
from ala.core.enums import _StrEnum


class EventType(_StrEnum):
    QUIZ = "quiz"
    EXAM = "exam"
    LESSON = "lesson"
    VIDEO = "video"
    READING = "reading"
    INTERACTION = "interaction"     # asked a question (GraphRAG)


@dataclass
class StudentProfile:
    student_id: str
    name: str = ""
    level: str = "beginner"                 # beginner | intermediate | advanced
    preferred_language: str = "en"
    explanation_style: str = "balanced"     # concise | balanced | detailed | example-driven
    difficulty_preference: str = "adaptive"  # easy | adaptive | challenging
    learning_pace: str = "normal"           # slow | normal | fast
    goals: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utcnow_iso)
    updated_at: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ConceptMastery:
    concept_id: str
    mastery: float = 0.3                     # [0,1]; 0.3 = unseen-but-not-zero prior
    attempts: int = 0
    correct: int = 0
    last_seen: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class LearningEvent:
    student_id: str
    type: str
    ref: str = ""                            # resource_id / quiz id / question
    concept_ids: list[str] = field(default_factory=list)
    score: float | None = None               # quiz/exam correctness [0,1]; None = exposure
    difficulty: float = 0.5                  # [0,1]
    timestamp: str = field(default_factory=utcnow_iso)

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class StudentConfig:
    location: str = "data/student/student.db"
    mastery_k: float = 0.25
    weak_threshold: float = 0.40
    strong_threshold: float = 0.70
    weak_weight: float = 0.5
    pref_weight: float = 0.2
    candidate_k: int = 40

    @classmethod
    def from_settings(cls, settings) -> "StudentConfig":
        s = (getattr(settings, "student", None) or {}) if settings else {}
        p = s.get("personalization", {}) or {}
        return cls(
            location=str(s.get("location", "data/student/student.db")),
            mastery_k=float(s.get("mastery_k", 0.25)),
            weak_threshold=float(s.get("weak_threshold", 0.40)),
            strong_threshold=float(s.get("strong_threshold", 0.70)),
            weak_weight=float(p.get("weak_weight", 0.5)),
            pref_weight=float(p.get("pref_weight", 0.2)),
            candidate_k=int(p.get("candidate_k", 40)),
        )
