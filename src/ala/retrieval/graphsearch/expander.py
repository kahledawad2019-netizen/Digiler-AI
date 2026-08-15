"""Graph expansion — multi-hop weighted traversal with relationship + path scoring.

Best-first BFS over concept↔concept edges. A concept reached through a stronger
relationship (or fewer hops) keeps the higher score; every concept records the
path that reached it (provenance preservation). Bounded by ``max_hops`` (depth),
``beam`` (frontier width) and ``max_expanded`` (total).
"""

from __future__ import annotations

from ala.graph.graph import ConceptGraph
from ala.retrieval.graphsearch.config import CONCEPT_EDGE_TYPES, GraphRetrievalConfig
from ala.retrieval.graphsearch.models import ExpandedConcept


class GraphExpander:
    def __init__(self, graph: ConceptGraph, config: GraphRetrievalConfig) -> None:
        self.graph = graph
        self.config = config

    def _edge_types(self) -> set[str]:
        return self.config.allowed_edge_types or CONCEPT_EDGE_TYPES

    def _label(self, cid: str) -> str:
        node = self.graph.node(cid)
        return node.label if node else cid

    def expand(self, seeds: dict[str, float]) -> dict[str, ExpandedConcept]:
        cfg = self.config
        edge_types = self._edge_types()
        result: dict[str, ExpandedConcept] = {}
        for cid, s in seeds.items():
            result[cid] = ExpandedConcept(cid, self._label(cid), float(s), 0, "seed", [cid])

        frontier: list[tuple[str, float]] = list(seeds.items())
        for hop in range(1, cfg.max_hops + 1):
            nxt: list[tuple[str, float]] = []
            for cid, score in frontier:
                for nb, etype, data in self.graph.neighbors(cid, edge_types=edge_types):
                    if not nb.startswith("concept:"):
                        continue
                    w = cfg.edge_weights.get(etype, 0.3)
                    if w < cfg.min_edge_weight:
                        continue
                    new_score = score * cfg.hop_decay * (1.0 if cfg.strategy == "bfs" else w)
                    prev = result.get(nb)
                    if prev is None or prev.score < new_score:
                        result[nb] = ExpandedConcept(
                            nb, self._label(nb), new_score, hop, etype,
                            result[cid].path + [nb])
                        nxt.append((nb, new_score))
            frontier = sorted(nxt, key=lambda kv: kv[1], reverse=True)[:cfg.beam]
            if not frontier:
                break

        top = sorted(result.values(), key=lambda e: e.score, reverse=True)[:cfg.max_expanded]
        return {e.concept_id: e for e in top}
