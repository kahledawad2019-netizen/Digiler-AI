"""Stage 12 — GraphRAG tests.

Component tests (context builder, prompt builder, citation/grounding, extractive
generator) run on hand-built Evidence Packages. Merge + end-to-end tests use a
small synthetic graph + stub hybrid. One real-corpus integration test runs the
full service when the built artifacts are present. No network (LLM adapter is a
seam, never called here).
"""

from __future__ import annotations

import pytest

from ala.config.settings import load_settings
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.rag.citations import GraphCitationManager
from ala.rag.context import GraphContextBuilder
from ala.rag.llm import ExtractiveGroundedGenerator
from ala.rag.merger import GraphEvidenceMerger
from ala.rag.models import GraphRAGConfig
from ala.rag.pipeline import GraphRAGPipeline
from ala.rag.prompt import GraphPromptBuilder
from ala.retrieval.evidence.builder import EvidenceBuilder
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, GraphEvidenceItem
from ala.retrieval.graphsearch.config import GraphRetrievalConfig
from ala.retrieval.graphsearch.retriever import GraphRetriever
from ala.retrieval.types import RetrievalResult


# --------------------------------------------------------------------------- #
def _package() -> EvidencePackage:
    items = [
        EvidenceItem(rank=0, chunk_id="a", text="A convolutional neural network uses convolution "
                     "and pooling to classify images.", retrieval_score=0.9, confidence=0.9,
                     resource_id="dl1", page=3, source_type="pdf", citation="[dl1, p.3]",
                     heading="CNNs"),
        EvidenceItem(rank=1, chunk_id="b", text="Pooling reduces the spatial size of the feature map.",
                     retrieval_score=0.8, confidence=0.8, resource_id="dl2", slide=5,
                     source_type="slide", citation="[dl2, slide 5]", heading="Pooling"),
        EvidenceItem(rank=2, chunk_id="c", text="Pooling reduces the spatial size of the feature map.",
                     retrieval_score=0.7, confidence=0.7, resource_id="dl2", slide=5,
                     source_type="slide", citation="[dl2, slide 5]", heading="Pooling"),  # dup
    ]
    gev = [
        GraphEvidenceItem(concept_id="concept:cnn", concept="Convolutional Neural Network",
                          score=1.0, hop=0, relationship="seed", path=["Convolutional Neural Network"],
                          source_resources=["dl1"], confidence=1.0),
        GraphEvidenceItem(concept_id="concept:pool", concept="Pooling", score=0.3, hop=1,
                          relationship="related_to",
                          path=["Convolutional Neural Network", "Pooling"],
                          source_resources=["dl2"], confidence=0.7),
        GraphEvidenceItem(concept_id="concept:nn", concept="Neural Network", score=0.9, hop=1,
                          relationship="prerequisite",
                          path=["Convolutional Neural Network", "Neural Network"],
                          source_resources=["dl1"], confidence=0.9),
    ]
    return EvidencePackage(query="what is pooling in a cnn", normalized_query="pooling cnn",
                           retriever="graphrag", items=items, graph_evidence=gev,
                           overall_confidence=0.85)


# -- context builder -------------------------------------------------------- #
def test_context_dedupe_cite_and_graph_scaffold():
    ctx = GraphContextBuilder(GraphRAGConfig()).build(_package())
    assert [c.cid for c in ctx.chunks] == ["C1", "C2"]        # 3rd is a duplicate → dropped
    assert ctx.concepts[0].cid == "K1"
    from ala.rag.models import ContextRelation
    assert ContextRelation("Convolutional Neural Network", "related_to", "Pooling") in ctx.relations
    assert "Neural Network" in ctx.prerequisites               # prerequisite relationship
    assert "Pooling" in ctx.neighbor_concepts                  # hop-1
    assert ctx.tokens_used > 0


def test_context_token_budget():
    ctx = GraphContextBuilder(GraphRAGConfig(token_budget=6, max_chunk_tokens=6)).build(_package())
    assert len(ctx.chunks) == 1                                # budget admits only the first


# -- prompt builder --------------------------------------------------------- #
def test_prompt_contains_rules_evidence_and_question():
    ctx = GraphContextBuilder().build(_package())
    prompt = GraphPromptBuilder().build(ctx)
    assert "ONLY the numbered evidence" in prompt
    assert "[C1]" in prompt and "[K1]" in prompt
    assert "# QUESTION" in prompt and ctx.question in prompt
    assert "# ANSWER" in prompt


# -- citation / grounding --------------------------------------------------- #
def test_grounding_detects_valid_and_invalid():
    cm = GraphCitationManager()
    ok = cm.check_grounding("CNNs pool features [C1]. Pooling shrinks maps [C2].", {"C1", "C2"})
    assert ok["grounding_ratio"] == 1.0 and ok["citation_valid"]
    bad = cm.check_grounding("This is made up [C9]. And this too.", {"C1"})
    assert not bad["citation_valid"] and bad["grounding_ratio"] < 1.0


# -- extractive generator (no hallucination) -------------------------------- #
def test_extractive_generator_is_grounded():
    ctx = GraphContextBuilder().build(_package())
    text = ExtractiveGroundedGenerator().answer(ctx, "")
    g = GraphCitationManager().check_grounding(text, set(ctx.citations))
    assert g["citation_valid"] and g["grounding_ratio"] == 1.0
    assert "[C1]" in text                                      # cites real evidence


def test_extractive_generator_handles_empty_context():
    from ala.rag.models import ReasoningContext
    text = ExtractiveGroundedGenerator().answer(ReasoningContext(question="q"), "")
    assert "not contain enough information" in text


# -- synthetic graph + stub hybrid ------------------------------------------ #
class StubHybrid:
    def __init__(self, rows):
        self.rows = rows

    def retrieve(self, query, *, top_k=10, filters=None):
        out = []
        for i, (cid, rid, score, text, page) in enumerate(self.rows[:top_k]):
            out.append(RetrievalResult(chunk_id=cid, score=score, rank=i, source="hybrid",
                                       payload={"resource_id": rid, "page": page, "heading": "CNNs"},
                                       component_scores={"rrf": score, "bm25": score}, text=text))
        return out


@pytest.fixture()
def graph():
    g = ConceptGraph()
    g.add_node(GraphNode("concept:cnn", NodeType.CONCEPT.value, "Convolutional Neural Network",
                         {"aliases": ["cnn"], "confidence": 0.9}))
    g.add_node(GraphNode("concept:nn", NodeType.CONCEPT.value, "Neural Network",
                         {"aliases": ["neural network"], "confidence": 0.9}))
    for rid in ("dl1", "dl2"):
        g.add_node(GraphNode(f"resource:{rid}", NodeType.RESOURCE.value, rid, {"resource_id": rid}))
    g.add_edge(GraphEdge("concept:cnn", "resource:dl1", EdgeType.APPEARS_IN.value, provenance=["dl1"]))
    g.add_edge(GraphEdge("concept:nn", "resource:dl2", EdgeType.APPEARS_IN.value, provenance=["dl2"]))
    g.add_edge(GraphEdge("concept:cnn", "concept:nn", EdgeType.RELATED_TO.value, weight=4.0))
    return g


def _pipeline(graph):
    hybrid = StubHybrid([
        ("a", "dl1", 0.9, "A convolutional neural network (CNN) classifies images with convolution.", 1),
        ("b", "dl2", 0.8, "Neural networks are the basis of a CNN.", 2),
    ])
    gr = GraphRetriever(graph, hybrid, GraphRetrievalConfig(candidate_k=10))
    builder = EvidenceBuilder(gr, None, None, "graphrag")
    merger = GraphEvidenceMerger(gr, builder, GraphRAGConfig())
    return GraphRAGPipeline(merger, GraphContextBuilder(), GraphPromptBuilder())


def test_merger_carries_chunks_and_graph_evidence(graph):
    hybrid = StubHybrid([("a", "dl1", 0.9, "CNN text about convolution.", 1)])
    gr = GraphRetriever(graph, hybrid, GraphRetrievalConfig())
    merger = GraphEvidenceMerger(gr, EvidenceBuilder(gr, None, None, "graphrag"), GraphRAGConfig())
    pkg, res = merger.merge("convolutional neural network", top_k=5)
    assert pkg.items and pkg.graph_evidence
    assert pkg.retriever == "graphrag"


def test_end_to_end_grounded_answer(graph):
    ans = _pipeline(graph).answer("what is a convolutional neural network")
    assert ans.answer and ans.citations
    assert ans.grounding["citation_valid"]
    assert ans.grounding["grounding_ratio"] == 1.0            # extractive → fully grounded
    assert ans.reasoning_trace                                 # trace present
    assert ans.stats["n_sources"] >= 1


def test_citations_preserve_provenance(graph):
    _, ctx, pkg = _pipeline(graph).answer_with_context("convolutional neural network")
    c1 = ctx.citations["C1"]
    assert c1.resource_id == "dl1" and c1.page == 1           # page carried into the citation


# -- real corpus ------------------------------------------------------------ #
def test_real_corpus_graphrag():
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.rag.pipeline import GraphRAGService
    try:
        svc = GraphRAGService(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts not built")
    try:
        ans, ctx, pkg = svc.answer_with_context("what is gradient descent", top_k=6)
    finally:
        svc.close()
    assert ans.answer and ans.grounding["citation_valid"]
    assert ctx.chunks and pkg.graph_evidence
    # Extractive when no LLM is reachable (CI/offline); an LLM-backed generator
    # (e.g. "ollama:qwen3") when one is running. Either is a valid grounded answer.
    assert ans.generator == "extractive-grounded" or ":" in ans.generator
