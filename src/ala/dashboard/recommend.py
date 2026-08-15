"""RecommendationEngine — what should this learner do next?

Real logic over the Student Model + concept graph: review the weakest concepts
(with the resources that teach them), practise concepts seen too few times, and
explore new concepts that build on the learner's strengths (``related_to``
neighbours of mastered concepts). No fabricated advice — every recommendation is
grounded in mastery + graph structure.
"""

from __future__ import annotations

from ala.dashboard.models import DashboardConfig, Recommendation
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, NodeType
from ala.student.model import StudentModel

_PROV = {EdgeType.APPEARS_IN.value, EdgeType.EXPLAINS.value, EdgeType.MENTIONED_IN.value}


class RecommendationEngine:
    def __init__(self, graph: ConceptGraph, student_model: StudentModel,
                 config: DashboardConfig | None = None) -> None:
        self.graph = graph
        self.sm = student_model
        self.config = config or DashboardConfig()

    def _label(self, cid: str) -> str:
        n = self.graph.node(cid)
        return n.label if n else cid.replace("concept:", "")

    def _resources(self, cid: str, k: int = 3) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for nb, _et, _d in self.graph.neighbors(cid, edge_types=_PROV):
            if nb.startswith("resource:") and nb not in seen:
                seen.add(nb)
                node = self.graph.node(nb)
                out.append({"resource_id": nb[len("resource:"):],
                            "title": node.label if node else nb})
            if len(out) >= k:
                break
        return out

    def recommend(self, student_id: str) -> list[Recommendation]:
        recs: list[Recommendation] = []
        weak = self.sm.weak_concepts(student_id)
        for cm in weak[: self.config.recommend_k]:
            practice = cm.attempts < 3
            recs.append(Recommendation(
                kind="practice" if practice else "review",
                concept=self._label(cm.concept_id), concept_id=cm.concept_id,
                reason=(f"seen only {cm.attempts} time(s)" if practice
                        else f"mastery {cm.mastery:.2f} is below target"),
                mastery=round(cm.mastery, 3), resources=self._resources(cm.concept_id)))

        seen = {cm.concept_id for cm in self.sm.store.all_mastery(student_id)}
        for cm in self.sm.strong_concepts(student_id)[:4]:
            for nb, _et, _d in self.graph.neighbors(cm.concept_id,
                                                    edge_types={EdgeType.RELATED_TO.value}):
                if nb.startswith("concept:") and nb not in seen and self.graph.node(nb):
                    recs.append(Recommendation(
                        kind="explore", concept=self._label(nb), concept_id=nb,
                        reason=f"builds on your strong {self._label(cm.concept_id)}",
                        mastery=0.0, resources=self._resources(nb)))
                    seen.add(nb)
                    break
            if sum(r.kind == "explore" for r in recs) >= 3:
                break
        return recs
