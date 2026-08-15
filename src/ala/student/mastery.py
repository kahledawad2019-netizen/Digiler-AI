"""MasteryModel — update per-concept mastery from learning events.

Mastery is a bounded [0,1] competence estimate updated toward the event outcome at
a difficulty-scaled learning rate (an Elo-flavoured EMA). Assessment events (quiz /
exam) carry the strongest signal; exposure events (lesson / video / reading /
interaction) nudge mastery up gently. Weak/strong are thresholds on mastery.
"""

from __future__ import annotations

from ala.core.clock import utcnow_iso
from ala.student.models import ConceptMastery, EventType, StudentConfig

# assessment vs exposure signal weights per event type
_SIGNAL = {EventType.QUIZ.value: 1.0, EventType.EXAM.value: 1.3,
           EventType.LESSON.value: 0.35, EventType.VIDEO.value: 0.35,
           EventType.READING.value: 0.25, EventType.INTERACTION.value: 0.2}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


class MasteryModel:
    def __init__(self, config: StudentConfig | None = None) -> None:
        self.config = config or StudentConfig()

    def update(self, cm: ConceptMastery, *, kind: str, score: float | None,
               difficulty: float = 0.5) -> ConceptMastery:
        signal = _SIGNAL.get(kind, 0.2)
        if score is None:                                     # exposure → gentle gain
            cm.mastery = _clamp(cm.mastery + 0.05 * signal * (1.0 - cm.mastery))
        else:                                                 # assessment → move to outcome
            k = self.config.mastery_k * signal * (0.5 + difficulty)
            cm.mastery = _clamp(cm.mastery + k * (score - cm.mastery))
            cm.correct += int(score >= 0.5)
        cm.attempts += 1
        cm.last_seen = utcnow_iso()
        return cm

    def is_weak(self, cm: ConceptMastery) -> bool:
        return cm.mastery < self.config.weak_threshold

    def is_strong(self, cm: ConceptMastery) -> bool:
        return cm.mastery >= self.config.strong_threshold
