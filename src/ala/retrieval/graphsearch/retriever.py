"""GraphRetriever — hybrid seeds + concept-graph expansion → graph-aware chunks.

Implements the ``Retriever`` protocol (``retrieve`` → ``list[RetrievalResult]``)
so it drops into the existing pipeline/eval harness unchanged, and adds
``retrieve_with_graph`` which additionally returns the concept-path graph
evidence for the Evidence Package (Stage 9 → Stage 12).

Ranking (graph-aware): each hybrid candidate keeps its fused score and gains a
graph boost = ``graph_weight × normalised graph-reachability of its resource``.
Chunks whose resource is reachable from the query's concepts rise; citations and
component scores are preserved (``component_scores['graph']`` is recorded).
"""

from __future__ import annotations

import time

from ala.graph.graph import ConceptGraph
from ala.retrieval.evidence.models import GraphEvidenceItem
from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES, GraphRetrievalConfig
from ala.retrieval.graphsearch.expander import GraphExpander
from ala.retrieval.graphsearch.linker import QueryConceptLinker
from ala.retrieval.graphsearch.models import GraphRetrievalResult
from ala.retrieval.types import RetrievalResult, Retriever


class GraphRetriever:
    def __init__(self, graph: ConceptGraph, hybrid: Retriever,
                 config: GraphRetrievalConfig | None = None,
                 linker: QueryConceptLinker | None = None,
                 expander: GraphExpander | None = None) -> None:
        self.graph = graph
        self.hybrid = hybrid
        self.config = config or GraphRetrievalConfig()
        self.linker = linker or QueryConceptLinker(graph)
        self.expander = expander or GraphExpander(graph, self.config)

    # -- Retriever protocol ---------------------------------------------- #
    def retrieve(self, query: str, *, top_k: int = 10,
                 filters: dict | None = None) -> list[RetrievalResult]:
        return self.retrieve_with_graph(query, top_k=top_k, filters=filters).chunks

    # -- full graph retrieval -------------------------------------------- #
    def retrieve_with_graph(self, query: str, *, top_k: int = 10,
                            filters: dict | None = None) -> GraphRetrievalResult:
        cfg = self.config
        t0 = time.perf_counter()

        seeds = self.hybrid.retrieve(query, top_k=cfg.candidate_k, filters=filters)
        n = len(seeds) or 1
        seed_res: list[tuple[str, float]] = []
        seen: set[str] = set()
        for i, r in enumerate(seeds):
            rid = r.payload.get("resource_id")
            if rid and rid not in seen:
                seen.add(rid)
                seed_res.append((rid, 1.0 - i / n))

        seed_concepts = self.linker.link(query, seed_resources=seed_res, top_k=cfg.top_concepts)
        expanded = self.expander.expand(seed_concepts)

        # per-resource graph score from expanded concepts' provenance edges
        resource_score: dict[str, float] = {}
        concept_resources: dict[str, list[str]] = {}
        for cid, ec in expanded.items():
            rids: list[str] = []
            for nb, _etype, _data in self.graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES):
                if nb.startswith("resource:"):
                    rid = nb[len("resource:"):]
                    rids.append(rid)
                    resource_score[rid] = max(resource_score.get(rid, 0.0), ec.score)
            concept_resources[cid] = rids

        # graph-aware re-rank of the hybrid candidates (provenance preserved)
        max_gs = max(resource_score.values(), default=0.0) or 1.0
        for r in seeds:
            gs = resource_score.get(r.payload.get("resource_id"), 0.0) / max_gs
            r.component_scores["graph"] = round(gs, 4)
            r.score = r.score + cfg.graph_weight * gs
            if gs > 0 and r.source in ("hybrid", "dense", "bm25"):
                r.source = "graph+" + r.source
        ranked = sorted(seeds, key=lambda r: r.score, reverse=True)[:top_k]
        for i, r in enumerate(ranked):
            r.rank = i

        # graph evidence (concept-path reasoning, ranked by expansion score)
        gev: list[GraphEvidenceItem] = []
        for ec in sorted(expanded.values(), key=lambda e: e.score, reverse=True)[:cfg.max_graph_evidence]:
            node = self.graph.node(ec.concept_id)
            conf = float(node.attrs.get("confidence", 0.0)) if node else 0.0
            gev.append(GraphEvidenceItem(
                concept_id=ec.concept_id, concept=ec.label, score=round(ec.score, 4),
                hop=ec.hop, relationship=ec.relationship,
                path=[self.expander._label(c) for c in ec.path],
                source_resources=concept_resources.get(ec.concept_id, [])[:10],
                confidence=round(conf, 4)))

        stats = {
            "seed_concepts": len(seed_concepts),
            "expanded_concepts": len(expanded),
            "graph_resources": len(resource_score),
            "max_hop": max((e.hop for e in expanded.values()), default=0),
            "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
        }
        return GraphRetrievalResult(query=query, chunks=ranked, graph_evidence=gev,
                                    seed_concepts=seed_concepts, expanded=expanded, stats=stats)
