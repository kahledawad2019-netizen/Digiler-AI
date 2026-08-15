"""Learner analytics — mastery distribution, weak/strong, timeline, confidence, progress."""

from __future__ import annotations

from collections import Counter

from ala.student.model import StudentModel


def compute_analytics(model: StudentModel, student_id: str, *, graph=None) -> dict:
    mastery = model.store.all_mastery(student_id)
    events = model.store.list_events(student_id)

    def label(cid: str) -> str:
        if graph is not None and graph.node(cid):
            return graph.node(cid).label
        return cid.replace("concept:", "")

    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
    hist = [0] * (len(bins) - 1)
    for cm in mastery:
        for i in range(len(bins) - 1):
            if bins[i] <= cm.mastery < bins[i + 1]:
                hist[i] += 1
                break

    weak = model.weak_concepts(student_id)
    strong = model.strong_concepts(student_id)

    # confidence history = assessment scores over time
    conf = [{"t": e.timestamp, "score": e.score} for e in events if e.score is not None]

    return {
        "summary": model.mastery_summary(student_id),
        "mastery_histogram": {"bins": ["0-.2", ".2-.4", ".4-.6", ".6-.8", ".8-1"], "counts": hist},
        "weak_concepts": [{"concept": label(cm.concept_id), "mastery": round(cm.mastery, 3),
                           "attempts": cm.attempts} for cm in weak[:12]],
        "strong_concepts": [{"concept": label(cm.concept_id), "mastery": round(cm.mastery, 3),
                             "attempts": cm.attempts} for cm in strong[:12]],
        "progress": dict(Counter(e.type for e in events)),
        "confidence_history": conf,
        "timeline": [{"t": e.timestamp, "type": e.type, "n_concepts": len(e.concept_ids)}
                     for e in events],
    }
