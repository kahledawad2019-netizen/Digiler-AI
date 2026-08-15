"""Stage 13 — GraphRAG-evaluation metric tests (fast, hermetic).

The full cross-system suite runs on the real corpus via `ala graphrag-eval`; these
tests validate the metric maths (context precision/recall, grounding, faithfulness,
hallucination, completeness, aggregation) on hand-built contexts.
"""

from __future__ import annotations

from ala.rag.citations import GraphCitationManager
from ala.rag.evaluation import _agg, _answer_metrics, _terms
from ala.rag.models import ContextChunk, ContextRelation, ReasoningContext


def _ctx() -> ReasoningContext:
    ctx = ReasoningContext(question="what is a convolutional neural network")
    ctx.chunks = [
        ContextChunk(cid="C1", text="A convolutional neural network classifies images with convolution.",
                     citation="[dl1, p.3]", resource_id="dl1", source_type="pdf",
                     confidence=0.9, tokens=10),
        ContextChunk(cid="C2", text="Unrelated text about spreadsheets.", citation="[xl, p.1]",
                     resource_id="excel1", source_type="pdf", confidence=0.5, tokens=5),
    ]
    ctx.relations = [ContextRelation("Convolutional Neural Network", "related_to", "Pooling")]
    ctx.citations = {"C1": None, "C2": None}
    return ctx


def test_terms_drops_stopwords():
    assert "convolutional" in _terms("what is a convolutional network")
    assert "the" not in _terms("the network")


def test_answer_metrics_grounded_and_precise():
    ctx = _ctx()
    answer = "[C1] A convolutional neural network classifies images with convolution."
    m = _answer_metrics(ctx, answer, GraphCitationManager(), gold_resource="dl1")
    assert m["context_precision"] == 0.5        # 1 of 2 context chunks is the gold resource
    assert m["context_recall"] == 1.0
    assert m["citation_accuracy"] == 1.0
    assert m["grounding"] == 1.0 and m["hallucination"] == 0.0
    assert m["faithfulness"] == 1.0             # sentence copied from its cited chunk
    assert m["multi_hop"] == 1.0                # a relation is present
    assert 0.0 < m["completeness"] <= 1.0


def test_answer_metrics_detects_hallucination():
    ctx = _ctx()
    bad = "Neural networks were invented in 1650 by nobody in particular."   # no citation
    m = _answer_metrics(ctx, bad, GraphCitationManager(), gold_resource="dl1")
    assert m["grounding"] == 0.0 and m["hallucination"] == 1.0


def test_agg_averages_rows():
    out = _agg([{"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}])
    assert out == {"a": 0.5, "b": 0.5}
