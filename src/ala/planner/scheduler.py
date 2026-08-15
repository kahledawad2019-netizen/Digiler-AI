"""StudyPlanner — build an adaptive, time-budgeted study plan.

Selects target concepts (explicit / course / the learner's weak concepts), orders
them by **curriculum week (prerequisite) then weakness**, generates read/watch/
practice/quiz activities (weak concepts get extra practice + spaced revision),
scales time by difficulty, and packs everything into days within the daily budget
and deadline.
"""

from __future__ import annotations

import re

from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, NodeType
from ala.planner.models import (ActivityType, PlannerConfig, StudyActivity, StudyDay,
                                StudyGoal, StudyPlan)
from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
from ala.student.model import StudentModel

_READ = {"lecture_slides", "lesson_page", "textbook", "overview_note", "reference"}
_WATCH = {"video"}
_PRACTICE = {"assessment", "worksheet", "notebook"}
_WEEK = re.compile(r"(\d+)")


class StudyPlanner:
    def __init__(self, graph: ConceptGraph, student_model: StudentModel,
                 config: PlannerConfig | None = None) -> None:
        self.graph = graph
        self.sm = student_model
        self.config = config or PlannerConfig()
        self.weak_threshold = student_model.config.weak_threshold

    # ------------------------------------------------------------------ #
    def plan(self, student_id: str, goal: StudyGoal) -> StudyPlan:
        self._mastery_cache = {cm.concept_id: cm.mastery
                               for cm in self.sm.store.all_mastery(student_id)}
        concepts = self._select(student_id, goal)[: self.config.max_concepts]
        ordered = self._order(concepts)                     # [(cid, mastery, week, label)]

        plan = StudyPlan(goal=goal.description,
                         concepts=[{"concept": lbl, "mastery": round(m, 3), "week": wk}
                                   for _c, m, wk, lbl in ordered])
        days = [StudyDay(day=i + 1) for i in range(max(1, goal.deadline_days))]
        remaining = [goal.minutes_per_day] * len(days)
        first_day: dict[str, int] = {}
        revise: list[tuple[str, str]] = []                  # (concept_id, label)

        for cid, mastery, _wk, label in ordered:
            acts, needs_rev = self._activities(cid, mastery, label)
            placed_any = False
            for a in acts:
                di = self._place(days, remaining, a, goal.minutes_per_day)
                if di is None:
                    plan.unscheduled.append(f"{label} ({a.type})")
                    continue
                placed_any = True
                first_day.setdefault(cid, di)
            if placed_any and needs_rev:
                revise.append((cid, label))

        # spaced revision
        for cid, label in revise:
            start = first_day.get(cid, 0) + self.config.revision_gap_days
            rev = StudyActivity(ActivityType.REVISION.value, label, cid,
                                self.config.activity_minutes["revision"])
            di = self._place(days, remaining, rev, goal.minutes_per_day, start=start)
            if di is None:
                plan.unscheduled.append(f"{label} (revision)")

        plan.days = [d for d in days if d.activities]
        plan.stats = self._stats(plan, ordered, goal)
        return plan

    # -- concept selection + ordering ----------------------------------- #
    def _select(self, student_id: str, goal: StudyGoal) -> list[str]:
        if goal.concept_ids:
            return [c for c in goal.concept_ids if self.graph.has_node(c)]
        if goal.course:
            return [cid for cid in self.graph.nodes(NodeType.CONCEPT.value)
                    if self._course_of(cid) == goal.course]
        weak = [cm.concept_id for cm in self.sm.weak_concepts(student_id)
                if self.graph.has_node(cm.concept_id)]
        if weak:
            return weak
        # cold start: top concepts by frequency
        cands = [(cid, self.graph.node(cid).attrs.get("frequency", 0))
                 for cid in self.graph.nodes(NodeType.CONCEPT.value)]
        cands.sort(key=lambda kv: kv[1], reverse=True)
        return [c for c, _ in cands[:12]]

    def _order(self, cids: list[str]) -> list[tuple[str, float, int, str]]:
        out = []
        for cid in cids:
            node = self.graph.node(cid)
            out.append((cid, self._mastery(cid), self._week(cid), node.label if node else cid))
        out.sort(key=lambda t: (t[2], t[1]))                # week (prerequisite) asc, weakest first
        return out

    def _mastery(self, cid: str) -> float:
        return getattr(self, "_mastery_cache", {}).get(cid, 0.3)

    # -- activities ------------------------------------------------------ #
    def _activities(self, cid: str, mastery: float, label: str):
        res = self._resources(cid)
        diff = 1.0 + (1.0 - mastery) * 0.6                  # weaker → more time
        am = self.config.activity_minutes
        acts: list[StudyActivity] = []

        def mk(kind, pool, base):
            r = pool[0] if pool else None
            acts.append(StudyActivity(kind, label, cid, int(round(base * diff)),
                                      resource_id=r[0] if r else "", title=r[1] if r else ""))

        if res["read"]:
            mk(ActivityType.READ.value, res["read"], am["read"])
        if res["watch"]:
            mk(ActivityType.WATCH.value, res["watch"], am["watch"])
        acts.append(StudyActivity(ActivityType.QUIZ.value, label, cid, am["quiz"]))
        weak = mastery < self.weak_threshold
        if weak and self.config.weak_extra_practice and res["practice"]:
            mk(ActivityType.PRACTICE.value, res["practice"], am["practice"])
        return acts, weak

    def _resources(self, cid: str) -> dict:
        buckets = {"read": [], "watch": [], "practice": []}
        for nb, _et, _d in self.graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES):
            if not nb.startswith("resource:"):
                continue
            node = self.graph.node(nb)
            dt = (node.attrs.get("doc_type", "") if node else "").lower()
            rid = nb[len("resource:"):]
            item = (rid, node.label if node else rid)
            if dt in _WATCH:
                buckets["watch"].append(item)
            elif dt in _PRACTICE:
                buckets["practice"].append(item)
            elif dt in _READ:
                buckets["read"].append(item)
            else:
                buckets["read"].append(item)
        return buckets

    # -- scheduling helpers --------------------------------------------- #
    @staticmethod
    def _place(days, remaining, act, cap, *, start: int = 0) -> int | None:
        for i in range(start, len(days)):
            if remaining[i] >= act.minutes or not days[i].activities:
                days[i].activities.append(act)
                remaining[i] -= act.minutes
                return i
        return None

    def _course_of(self, cid: str) -> str | None:
        for nb, _et, _d in self.graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES):
            if nb.startswith("resource:") and self.graph.node(nb):
                c = self.graph.node(nb).attrs.get("course")
                if c:
                    return c
        return None

    def _week(self, cid: str) -> int:
        weeks = []
        for nb, _et, _d in self.graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES):
            if nb.startswith("resource:") and self.graph.node(nb):
                mod = str(self.graph.node(nb).attrs.get("module", ""))
                m = _WEEK.search(mod)
                if m:
                    weeks.append(int(m.group(1)))
        return min(weeks) if weeks else 99

    def _stats(self, plan: StudyPlan, ordered, goal: StudyGoal) -> dict:
        from collections import Counter
        acts = [a for d in plan.days for a in d.activities]
        weak_cids = {c for c, m, _w, _l in ordered if m < self.weak_threshold}
        weak_minutes = sum(a.minutes for a in acts if a.concept_id in weak_cids)
        return {
            "n_days_used": len(plan.days), "deadline_days": goal.deadline_days,
            "minutes_per_day": goal.minutes_per_day, "total_minutes": plan.total_minutes,
            "n_activities": len(acts), "by_activity": dict(Counter(a.type for a in acts)),
            "n_concepts": len(ordered), "n_weak": len(weak_cids),
            "weak_minutes_share": round(weak_minutes / plan.total_minutes, 3) if plan.total_minutes else 0.0,
            "n_unscheduled": len(plan.unscheduled),
            "fits_deadline": len(plan.days) <= goal.deadline_days,
            "max_day_minutes": max((d.minutes for d in plan.days), default=0),
        }
