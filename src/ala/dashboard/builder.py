"""DashboardBuilder — assemble the full DashboardData for a learner.

Composes Stage-18 analytics with graph-derived domain mastery + weak-concept
heatmap, catalog-derived completion rate, estimated time-spent, and confidence
evolution, plus the recommendation engine.
"""

from __future__ import annotations

from collections import defaultdict

from ala.dashboard.models import DashboardConfig, DashboardData
from ala.dashboard.recommend import RecommendationEngine
from ala.student.analytics import compute_analytics
from ala.student.model import StudentModel
from ala.student.models import EventType


class DashboardBuilder:
    def __init__(self, student_model: StudentModel, graph=None, catalog=None,
                 config: DashboardConfig | None = None) -> None:
        self.sm = student_model
        self.graph = graph
        self.catalog = catalog
        self.config = config or DashboardConfig()
        self.recommender = RecommendationEngine(graph, student_model, config) if graph else None

    def build(self, student_id: str) -> DashboardData:
        base = compute_analytics(self.sm, student_id, graph=self.graph)
        events = self.sm.store.list_events(student_id)
        mastery = self.sm.store.all_mastery(student_id)
        profile = self.sm.profile(student_id)

        # heatmap + domain mastery (from the graph's concept domains)
        heatmap = []
        by_domain: dict[str, list[float]] = defaultdict(list)
        for cm in sorted(mastery, key=lambda c: c.mastery):
            domain = "general"
            if self.graph is not None and self.graph.node(cm.concept_id):
                domain = self.graph.node(cm.concept_id).attrs.get("domain", "general")
                label = self.graph.node(cm.concept_id).label
            else:
                label = cm.concept_id.replace("concept:", "")
            heatmap.append({"concept": label, "domain": domain, "mastery": round(cm.mastery, 3)})
            by_domain[domain].append(cm.mastery)
        domain_mastery = [{"domain": d, "mastery": round(sum(v) / len(v), 3), "n": len(v)}
                          for d, v in sorted(by_domain.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))]

        # estimated time spent (event type × typical minutes)
        tm = self.config.typical_minutes
        spent: dict[str, float] = defaultdict(float)
        for e in events:
            spent[e.type] += tm.get(e.type, 5)
        time_spent = {"by_type": dict(spent), "total_minutes": round(sum(spent.values()), 1)}

        # completion (concept coverage + resource completion + per-course)
        completion = self._completion(events, mastery)

        # confidence evolution (assessment scores + running average)
        conf = []
        run: list[float] = []
        for e in events:
            if e.score is not None:
                run.append(e.score)
                conf.append({"t": e.timestamp, "score": round(e.score, 3),
                             "avg": round(sum(run) / len(run), 3)})

        recs = [r.to_dict() for r in self.recommender.recommend(student_id)] if self.recommender else []

        return DashboardData(
            student_id=student_id, profile=profile.to_dict() if profile else {},
            summary=base["summary"], mastery_distribution=base["mastery_histogram"],
            heatmap=heatmap, domain_mastery=domain_mastery,
            weak_concepts=base["weak_concepts"], strong_concepts=base["strong_concepts"],
            timeline=base["timeline"], progress=base["progress"], time_spent=time_spent,
            completion=completion, confidence_evolution=conf, recommendations=recs)

    # ------------------------------------------------------------------ #
    def _completion(self, events, mastery) -> dict:
        total_concepts = len(self.graph.nodes("concept")) if self.graph is not None else 0
        seen = len(mastery)
        resource_refs = {e.ref for e in events
                         if e.type in (EventType.LESSON.value, EventType.VIDEO.value,
                                       EventType.READING.value) and e.ref}
        by_course = self._by_course(resource_refs)
        return {
            "concepts_seen": seen, "concepts_total": total_concepts,
            "concept_coverage": round(seen / total_concepts, 4) if total_concepts else 0.0,
            "resources_completed": len(resource_refs), "by_course": by_course,
        }

    def _by_course(self, resource_refs: set[str]) -> list[dict]:
        if self.catalog is None:
            return []
        available: dict[str, int] = defaultdict(int)
        try:
            for row in self.catalog.list_all(record_status="active"):
                import json
                course = json.loads(row["metadata_json"]).get("course", "?")
                available[course] += 1
        except Exception:
            return []
        done: dict[str, int] = defaultdict(int)
        for rid in resource_refs:
            meta = self.catalog.get(rid)
            if meta:
                done[meta.course] += 1
        return [{"course": c, "completed": done.get(c, 0), "available": n,
                 "rate": round(done.get(c, 0) / n, 3) if n else 0.0}
                for c, n in sorted(available.items()) if done.get(c, 0) > 0]
