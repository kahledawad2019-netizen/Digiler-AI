"""StudentModel — high-level learner API over the store + mastery model.

Records longitudinal events (quiz/exam/lesson/video/reading/interaction), updates
per-concept mastery, and exposes the profile + weak/strong concepts that drive
personalised retrieval and analytics.
"""

from __future__ import annotations

from ala.student.mastery import MasteryModel
from ala.student.models import (ConceptMastery, EventType, LearningEvent,
                                StudentConfig, StudentProfile)
from ala.student.store import StudentStore


class StudentModel:
    def __init__(self, settings, *, store: StudentStore | None = None,
                 mastery: MasteryModel | None = None, config: StudentConfig | None = None) -> None:
        self.settings = settings
        self.config = config or StudentConfig.from_settings(settings)
        self.store = store or StudentStore.from_settings(settings)
        self.mastery = mastery or MasteryModel(self.config)

    # -- profile --------------------------------------------------------- #
    def get_or_create(self, student_id: str, **fields) -> StudentProfile:
        p = self.store.get_profile(student_id)
        if p is None:
            p = StudentProfile(student_id=student_id, **fields)
            self.store.upsert_profile(p)
        elif fields:
            for k, v in fields.items():
                setattr(p, k, v)
            self.store.upsert_profile(p)
        return p

    def profile(self, student_id: str) -> StudentProfile | None:
        return self.store.get_profile(student_id)

    # -- events ---------------------------------------------------------- #
    def record_event(self, student_id: str, type: str, concept_ids: list[str], *,
                     ref: str = "", score: float | None = None,
                     difficulty: float = 0.5) -> LearningEvent:
        e = LearningEvent(student_id=student_id, type=type, ref=ref,
                          concept_ids=list(concept_ids), score=score, difficulty=difficulty)
        self.store.add_event(e)
        for cid in concept_ids:
            cm = self.store.get_mastery(student_id, cid) or ConceptMastery(concept_id=cid)
            self.mastery.update(cm, kind=type, score=score, difficulty=difficulty)
            self.store.set_mastery(student_id, cm)
        return e

    def record_quiz(self, student_id: str, concept_ids: list[str], *, correct: bool,
                    difficulty: float = 0.5, ref: str = "") -> LearningEvent:
        return self.record_event(student_id, EventType.QUIZ.value, concept_ids,
                                 ref=ref, score=1.0 if correct else 0.0, difficulty=difficulty)

    def record_exposure(self, student_id: str, type: str, concept_ids: list[str], *,
                        ref: str = "") -> LearningEvent:
        return self.record_event(student_id, type, concept_ids, ref=ref, score=None)

    # -- summaries ------------------------------------------------------- #
    def mastery_of(self, student_id: str, concept_id: str) -> float:
        cm = self.store.get_mastery(student_id, concept_id)
        return cm.mastery if cm else ConceptMastery(concept_id).mastery

    def weak_concepts(self, student_id: str, *, k: int | None = None) -> list[ConceptMastery]:
        weak = [cm for cm in self.store.all_mastery(student_id) if self.mastery.is_weak(cm)]
        weak.sort(key=lambda cm: cm.mastery)
        return weak[:k] if k else weak

    def strong_concepts(self, student_id: str, *, k: int | None = None) -> list[ConceptMastery]:
        strong = [cm for cm in self.store.all_mastery(student_id) if self.mastery.is_strong(cm)]
        strong.sort(key=lambda cm: cm.mastery, reverse=True)
        return strong[:k] if k else strong

    def mastery_summary(self, student_id: str) -> dict:
        all_m = self.store.all_mastery(student_id)
        overall = round(sum(cm.mastery for cm in all_m) / len(all_m), 4) if all_m else 0.0
        events = self.store.list_events(student_id)
        from collections import Counter
        return {
            "student_id": student_id, "overall_mastery": overall, "n_tracked": len(all_m),
            "n_weak": len(self.weak_concepts(student_id)),
            "n_strong": len(self.strong_concepts(student_id)),
            "n_events": len(events),
            "events_by_type": dict(Counter(e.type for e in events)),
        }

    def close(self) -> None:
        self.store.close()
