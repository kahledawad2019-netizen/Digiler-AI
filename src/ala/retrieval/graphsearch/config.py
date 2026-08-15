"""Graph-retrieval configuration (config-over-hardcode).

Read from ``settings.graph.retrieval`` when present; every knob has a safe
default so the engine runs out of the box. Edge weights make traversal
*relationship-aware*: a ``prerequisite``/``explains`` hop is worth more than a
loose ``related_to`` co-occurrence hop.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.config.settings import Settings

# Relationship weights (V3 §4.5 — weighted edge traversal). Higher = stronger
# semantic pull during expansion / provenance scoring.
_DEFAULT_EDGE_WEIGHTS: dict[str, float] = {
    "prerequisite": 1.0,
    "depends_on": 0.85,
    "explains": 0.9,
    "related_to": 0.6,
    "example_of": 0.55,
    "appears_in": 0.7,
    "mentioned_in": 0.4,
    "contains": 0.3,
    "references": 0.5,
    "extends": 0.5,
}

# concept ↔ concept edges walked during expansion
CONCEPT_EDGE_TYPES: set[str] = {"related_to", "prerequisite", "depends_on", "extends"}
# concept ↔ resource edges used to collect provenance / score resources
PROVENANCE_EDGE_TYPES: set[str] = {"appears_in", "mentioned_in", "explains", "example_of"}


@dataclass
class GraphRetrievalConfig:
    max_hops: int = 2                     # traversal depth control
    hop_decay: float = 0.5                # score decay per hop
    graph_weight: float = 0.5             # weight of graph boost in re-ranking
    candidate_k: int = 30                 # hybrid candidates fetched + re-ranked
    top_concepts: int = 8                 # seed concepts kept from linking
    beam: int = 24                        # frontier cap per hop
    max_expanded: int = 60                # cap on total expanded concepts
    max_graph_evidence: int = 15          # graph-evidence items returned
    strategy: str = "weighted_bfs"        # weighted_bfs | bfs
    min_edge_weight: float = 0.0          # graph filtering: drop weak edges
    edge_weights: dict = field(default_factory=lambda: dict(_DEFAULT_EDGE_WEIGHTS))
    allowed_edge_types: set | None = None  # None = CONCEPT_EDGE_TYPES

    @classmethod
    def from_settings(cls, settings: Settings) -> "GraphRetrievalConfig":
        g = ((settings.graph or {}).get("retrieval") or {}) if settings.graph else {}
        ew = dict(_DEFAULT_EDGE_WEIGHTS)
        ew.update(g.get("edge_weights") or {})
        allowed = g.get("allowed_edge_types")
        return cls(
            max_hops=int(g.get("max_hops", 2)),
            hop_decay=float(g.get("hop_decay", 0.5)),
            graph_weight=float(g.get("graph_weight", 0.5)),
            candidate_k=int(g.get("candidate_k", 30)),
            top_concepts=int(g.get("top_concepts", 8)),
            beam=int(g.get("beam", 24)),
            max_expanded=int(g.get("max_expanded", 60)),
            max_graph_evidence=int(g.get("max_graph_evidence", 15)),
            strategy=str(g.get("strategy", "weighted_bfs")),
            min_edge_weight=float(g.get("min_edge_weight", 0.0)),
            edge_weights=ew,
            allowed_edge_types=set(allowed) if allowed else None,
        )
