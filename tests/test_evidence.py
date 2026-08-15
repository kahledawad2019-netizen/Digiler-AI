"""Stage 9 — Evidence Package tests."""

from __future__ import annotations

import pytest

from ala.retrieval.evidence import (
    EvidenceBuilder,
    EvidenceFormatter,
    EvidenceItem,
    EvidencePackage,
    EvidenceSerializer,
    EvidenceValidator,
    SourceType,
)
from ala.retrieval.types import RetrievalResult


class _FakeRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, query, *, top_k=10, filters=None):
        return self._results[:top_k]


def _results():
    return [
        RetrievalResult(
            "tech.dmv.w03.constraints::c0", 0.032, 0, "hybrid",
            payload={"resource_id": "tech.dmv.w03.constraints", "page": 5, "heading": "Keys",
                     "section_path": ["Keys"], "language": "en", "parent_id": "tech.dmv.w03.constraints::p0",
                     "chunk_type": "paragraph", "course": "dmv"},
            component_scores={"dense": 0.89, "dense_rank": 2, "bm25": 24.3, "bm25_rank": 1, "rrf": 0.032},
            text="A foreign key enforces referential integrity."),
        RetrievalResult(
            "tech.aiml.l06.knn::c3", 0.030, 1, "hybrid",
            payload={"resource_id": "tech.aiml.l06.knn", "slide": 7, "heading": "KNN",
                     "language": "en", "chunk_type": "slide"},
            component_scores={"bm25": 12.0, "bm25_rank": 2, "rrf": 0.030},
            text="KNN classifies by nearest neighbours."),
        RetrievalResult(
            "tech.aiml.v01.lecture::c9", 0.028, 2, "hybrid",
            payload={"resource_id": "tech.aiml.v01.lecture", "timestamp": 754, "language": "en"},
            component_scores={"dense": 0.80, "dense_rank": 1, "rrf": 0.028},
            text="At twelve minutes we cover attention."),
    ]


def _package():
    return EvidenceBuilder(_FakeRetriever(_results())).build("foreign key", top_k=3)


def test_builder_fields_and_source_types():
    pkg = _package()
    assert len(pkg.items) == 3
    assert pkg.items[0].source_type == SourceType.PDF.value
    assert pkg.items[1].source_type == SourceType.SLIDE.value
    assert pkg.items[2].source_type == SourceType.VIDEO.value
    it = pkg.items[0]
    assert it.dense_score == 0.89 and it.bm25_score == 24.3 and it.fused_score == 0.032
    assert it.semantic_similarity == 0.89
    assert it.parent_chunk == "tech.dmv.w03.constraints::p0"
    assert "dense" in it.retrieval_reason and "BM25" in it.retrieval_reason
    assert it.document_title  # derived from resource_id


def test_citations_typed():
    pkg = _package()
    assert "p.5" in pkg.items[0].citation
    assert "slide 7" in pkg.items[1].citation
    assert "12:34" in pkg.items[2].citation


def test_confidence_and_ordering():
    pkg = _package()
    assert all(0.0 <= it.confidence <= 1.0 for it in pkg.items)
    assert 0.0 <= pkg.overall_confidence <= 1.0
    fused = [it.fused_score for it in pkg.items]
    assert fused == sorted(fused, reverse=True)


def test_formatter_context_and_index():
    pkg = _package()
    ctx = EvidenceFormatter().to_context(pkg, include_scores=True)
    assert "[1]" in ctx and "p.5" in ctx and "cite" in ctx.lower()
    idx = EvidenceFormatter().citation_index(pkg)
    assert idx[0]["page"] == 5 and idx[1]["slide"] == 7 and idx[2]["timestamp"] == 754


def test_serialization_roundtrip_and_size():
    pkg = _package()
    js = EvidenceSerializer.to_json(pkg)
    restored = EvidenceSerializer.from_json(js)
    assert restored == pkg
    assert EvidenceSerializer.size_bytes(pkg) > 0


def test_validator_passes_wellformed():
    assert EvidenceValidator().validate(_package()).ok


def test_validator_catches_bad_citation_and_ordering():
    v = EvidenceValidator()
    # pdf source but no page
    bad = EvidencePackage(query="q", normalized_query="q", items=[
        EvidenceItem(rank=0, chunk_id="x::c0", text="t", retrieval_score=1.0, fused_score=1.0,
                     resource_id="x", citation="[x]", source_type=SourceType.PDF.value, page=None)])
    assert not v.validate(bad).ok

    # out-of-order fused scores
    unordered = EvidencePackage(query="q", normalized_query="q", items=[
        EvidenceItem(rank=0, chunk_id="a", text="t", retrieval_score=0.1, fused_score=0.1,
                     resource_id="a", citation="[a]"),
        EvidenceItem(rank=1, chunk_id="b", text="t", retrieval_score=0.9, fused_score=0.9,
                     resource_id="b", citation="[b]")])
    assert any("sorted" in i.message for i in v.validate(unordered).errors)


def test_missing_text_is_warning_not_error():
    pkg = EvidencePackage(query="q", normalized_query="q", items=[
        EvidenceItem(rank=0, chunk_id="a::c0", text="  ", retrieval_score=0.1, fused_score=0.1,
                     resource_id="a", citation="[a]", source_type=SourceType.DOCUMENT.value)])
    res = EvidenceValidator().validate(pkg)
    assert res.ok and any("empty text" in w.message for w in res.warnings)
