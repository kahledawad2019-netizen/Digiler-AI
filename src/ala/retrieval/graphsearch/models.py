"""Value types for graph retrieval (chunk evidence + graph evidence)."""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.retrieval.evidence.models import GraphEvidenceItem
from ala.retrieval.types import RetrievalResult


@dataclass
class ExpandedConcept:
    """A concept reached during expansion, with its provenance path + score."""

    concept_id: str
    label: str
    score: float
    hop: int                      # 0 = seed, 1 = 1-hop neighbour, …
    relationship: str             # edge type that reached it ("seed" for seeds)
    path: list[str] = field(default_factory=list)   # concept ids along the path (incl. self)


@dataclass
class GraphRetrievalResult:
    """Everything a graph query produces: graph-aware chunks + graph evidence."""

    query: str
    chunks: list[RetrievalResult]                    # graph-aware re-ranked (citations preserved)
    graph_evidence: list[GraphEvidenceItem]          # the concept-path reasoning
    seed_concepts: dict[str, float]                  # concept_id → seed score
    expanded: dict[str, ExpandedConcept]             # concept_id → ExpandedConcept
    stats: dict = field(default_factory=dict)
