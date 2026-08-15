"""PersonalizedRetriever — remediation-aware re-ranking for a learner.

Wraps any ``Retriever`` (additive, same protocol) and nudges results toward the
learner's **weak concepts** (resources that teach them, via the concept graph) plus
their **preferences** (language / explanation style). Weak-concept remediation is
the pedagogical goal: when a learner asks a broad question, surface the material
that shores up what they are weak on. ``component_scores['student']`` records the
adjustment so it stays explainable.
"""

from __future__ import annotations

from ala.graph.graph import ConceptGraph
from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
from ala.retrieval.types import RetrievalResult, Retriever
from ala.student.model import StudentModel
from ala.student.models import StudentConfig

_STYLE_DOCTYPE = {"example-driven": {"assessment", "worksheet", "notebook"},
                  "detailed": {"textbook", "lesson_page"}}


class PersonalizedRetriever:
    def __init__(self, base: Retriever, student_model: StudentModel, student_id: str,
                 graph: ConceptGraph, config: StudentConfig | None = None) -> None:
        self.base = base
        self.student_id = student_id
        self.graph = graph
        self.config = config or student_model.config
        self.profile = student_model.profile(student_id)
        self.weak_resources = self._weak_resources(student_model)

    def _weak_resources(self, sm: StudentModel) -> set[str]:
        out: set[str] = set()
        for cm in sm.weak_concepts(self.student_id):
            if not self.graph.has_node(cm.concept_id):
                continue
            for nb, _et, _d in self.graph.neighbors(cm.concept_id, edge_types=PROVENANCE_EDGE_TYPES):
                if nb.startswith("resource:"):
                    out.add(nb[len("resource:"):])
        return out

    # -- Retriever protocol --------------------------------------------- #
    def retrieve(self, query: str, *, top_k: int = 10,
                 filters: dict | None = None) -> list[RetrievalResult]:
        cfg = self.config
        results = self.base.retrieve(query, top_k=cfg.candidate_k, filters=filters)
        pref_types = _STYLE_DOCTYPE.get((self.profile.explanation_style if self.profile else ""), set())
        for r in results:
            p = r.payload
            weak = 1.0 if p.get("resource_id") in self.weak_resources else 0.0
            pref = 0.0
            if self.profile and p.get("language") == self.profile.preferred_language:
                pref += 0.5
            if pref_types and p.get("doc_type") in pref_types:
                pref += 0.5
            adj = round(cfg.weak_weight * weak + cfg.pref_weight * min(1.0, pref), 4)
            r.component_scores["student"] = adj
            r.score += adj
            if weak > 0 and r.source in ("hybrid", "dense", "bm25", "graph+hybrid"):
                r.source = "personalized"
        results.sort(key=lambda r: r.score, reverse=True)
        for i, r in enumerate(results[:top_k]):
            r.rank = i
        return results[:top_k]
