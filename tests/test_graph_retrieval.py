"""Stage 11 — Graph Retrieval tests.

Unit/traversal/ranking/evidence/edge-scoring/concept-expansion tests run on a
small synthetic graph + a stub hybrid retriever (fast, hermetic). One real-corpus
integration test runs the full engine when the built artifacts are present.
"""

from __future__ import annotations

import pytest

from ala.config.settings import load_settings
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.retrieval.evidence.models import EvidencePackage, GraphEvidenceItem
from ala.retrieval.graphsearch.config import GraphRetrievalConfig
from ala.retrieval.graphsearch.expander import GraphExpander
from ala.retrieval.graphsearch.linker import QueryConceptLinker
from ala.retrieval.graphsearch.retriever import GraphRetriever
from ala.retrieval.types import RetrievalResult


# --------------------------------------------------------------------------- #
def _concept(cid, label, aliases):
    return GraphNode(cid, NodeType.CONCEPT.value, label,
                     {"aliases": aliases, "confidence": 0.9, "frequency": 10})


@pytest.fixture()
def graph() -> ConceptGraph:
    g = ConceptGraph()
    g.add_node(_concept("concept:cnn", "Convolutional Neural Network", ["cnn", "convnet"]))
    g.add_node(_concept("concept:nn", "Neural Network", ["neural network"]))
    g.add_node(_concept("concept:relu", "Activation Function", ["activation function", "relu"]))
    g.add_node(_concept("concept:sql", "SQL Join", ["sql join", "join"]))
    for rid in ("dl1", "dl2", "db1"):
        g.add_node(GraphNode(f"resource:{rid}", NodeType.RESOURCE.value, rid, {"resource_id": rid}))
    # concept -> resource provenance
    g.add_edge(GraphEdge("concept:cnn", "resource:dl1", EdgeType.APPEARS_IN.value, provenance=["dl1"]))
    g.add_edge(GraphEdge("concept:cnn", "resource:dl2", EdgeType.MENTIONED_IN.value, provenance=["dl2"]))
    g.add_edge(GraphEdge("concept:nn", "resource:dl1", EdgeType.APPEARS_IN.value, provenance=["dl1"]))
    g.add_edge(GraphEdge("concept:relu", "resource:dl2", EdgeType.APPEARS_IN.value, provenance=["dl2"]))
    g.add_edge(GraphEdge("concept:sql", "resource:db1", EdgeType.APPEARS_IN.value, provenance=["db1"]))
    # concept <-> concept
    g.add_edge(GraphEdge("concept:cnn", "concept:nn", EdgeType.RELATED_TO.value, weight=5.0))
    g.add_edge(GraphEdge("concept:cnn", "concept:relu", EdgeType.RELATED_TO.value, weight=3.0))
    g.add_edge(GraphEdge("concept:nn", "concept:relu", EdgeType.RELATED_TO.value, weight=2.0))
    return g


class StubHybrid:
    """Deterministic Retriever returning chunks from fixed resources."""

    def __init__(self, rows):  # rows: list[(chunk_id, resource_id, score)]
        self.rows = rows

    def retrieve(self, query, *, top_k=10, filters=None):
        out = []
        for i, (cid, rid, score) in enumerate(self.rows[:top_k]):
            out.append(RetrievalResult(chunk_id=cid, score=score, rank=i, source="hybrid",
                                       payload={"resource_id": rid},
                                       component_scores={"rrf": score}))
        return out


# -- linker ----------------------------------------------------------------- #
def test_linker_matches_query_alias(graph):
    linker = QueryConceptLinker(graph)
    scores = linker.link("explain the cnn architecture", top_k=8)
    assert "concept:cnn" in scores and scores["concept:cnn"] == 1.0


def test_linker_from_seed_resources(graph):
    linker = QueryConceptLinker(graph)
    scores = linker.link("no direct concept words here", seed_resources=[("dl1", 1.0)])
    # dl1 has cnn + nn attached
    assert {"concept:cnn", "concept:nn"} <= set(scores)


# -- expander (traversal / concept expansion / edge scoring) ---------------- #
def test_expander_multi_hop_paths(graph):
    cfg = GraphRetrievalConfig(max_hops=1, hop_decay=0.5)
    exp = GraphExpander(graph, cfg).expand({"concept:cnn": 1.0})
    assert exp["concept:cnn"].hop == 0
    assert "concept:nn" in exp and exp["concept:nn"].hop == 1
    assert exp["concept:nn"].path == ["concept:cnn", "concept:nn"]


def test_expander_depth_control(graph):
    # sql is disconnected from cnn's component → never reached
    exp = GraphExpander(graph, GraphRetrievalConfig(max_hops=3)).expand({"concept:cnn": 1.0})
    assert "concept:sql" not in exp


def test_expander_weighted_edge_scoring(graph):
    # related_to nn (w) reached from cnn; give prerequisite a higher weight and add one
    graph.add_edge(GraphEdge("concept:cnn", "concept:sql", EdgeType.PREREQUISITE.value, weight=1.0))
    cfg = GraphRetrievalConfig(max_hops=1, hop_decay=1.0,
                               edge_weights={"related_to": 0.4, "prerequisite": 1.0},
                               allowed_edge_types={"related_to", "prerequisite"})
    exp = GraphExpander(graph, cfg).expand({"concept:cnn": 1.0})
    # prerequisite hop (1.0) must outscore related_to hop (0.4)
    assert exp["concept:sql"].score > exp["concept:nn"].score
    assert exp["concept:sql"].relationship == "prerequisite"


# -- retriever (ranking / evidence / provenance) ---------------------------- #
def test_graph_aware_ranking_boosts_reachable(graph):
    hybrid = StubHybrid([("c_db", "db1", 0.9), ("c_dl", "dl1", 0.8), ("c_dl2", "dl2", 0.7)])
    gr = GraphRetriever(graph, hybrid, GraphRetrievalConfig(graph_weight=0.5, candidate_k=10))
    res = gr.retrieve_with_graph("convolutional neural network", top_k=3)
    top = res.chunks[0]
    # dl1 (strongly graph-reachable from cnn/nn) is promoted above db1 despite lower base score
    assert top.payload["resource_id"] == "dl1"
    assert "graph" in top.component_scores


def test_graph_evidence_and_citations_preserved(graph):
    hybrid = StubHybrid([("c_dl", "dl1", 0.8)])
    gr = GraphRetriever(graph, hybrid, GraphRetrievalConfig())
    res = gr.retrieve_with_graph("cnn", top_k=3)
    assert res.graph_evidence and isinstance(res.graph_evidence[0], GraphEvidenceItem)
    seed = res.graph_evidence[0]
    assert seed.concept and seed.path and seed.relationship == "seed"
    # citations preserved on chunk evidence
    assert res.chunks[0].citation().startswith("[dl1")


def test_evidence_package_accepts_graph_evidence(graph):
    hybrid = StubHybrid([("c_dl", "dl1", 0.8)])
    res = GraphRetriever(graph, hybrid).retrieve_with_graph("cnn", top_k=3)
    pkg = EvidencePackage(query="cnn", normalized_query="cnn", retriever="graph",
                          graph_evidence=res.graph_evidence)
    round_trip = EvidencePackage.from_dict(pkg.to_dict())
    assert round_trip.graph_evidence[0].concept == res.graph_evidence[0].concept


# -- real-corpus integration ------------------------------------------------ #
def test_real_corpus_graph_retrieval():
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.retrieval.graphsearch.factory import build_graph_retriever
    try:
        bundle = build_graph_retriever(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts (qdrant/bm25) not built")
    try:
        res = bundle.graph.retrieve_with_graph("gradient descent", top_k=5)
    finally:
        bundle.close()
    assert res.chunks and res.seed_concepts
    assert all("graph" in r.component_scores for r in res.chunks)
    assert res.stats["expanded_concepts"] >= res.stats["seed_concepts"]
