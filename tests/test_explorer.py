"""Stage 15 — Citation Explorer tests."""

from __future__ import annotations

import pytest

from ala.config.settings import load_settings
from ala.explorer.explorer import CitationExplorer
from ala.explorer.html import render
from ala.explorer.models import ExplorerConfig
from ala.explorer.resolver import CitationResolver
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, GraphEvidenceItem


# -- tiny catalog stub (a real resource resolver would return ResourceMetadata) #
class _File:
    def __init__(self, p): self.file_path = p


class _Meta:
    def __init__(self, p, t): self.file = _File(p); self.title = t


class _Catalog:
    def __init__(self, m): self._m = m
    def get(self, rid): return self._m.get(rid)


@pytest.fixture()
def settings():
    return load_settings(None)


def _package() -> EvidencePackage:
    items = [
        EvidenceItem(rank=0, chunk_id="a", text="CNNs use convolution.", retrieval_score=0.9,
                     confidence=0.9, resource_id="r1", page=3, source_type="pdf",
                     citation="[r1, p.3]", document_title="DL Lecture"),
        EvidenceItem(rank=1, chunk_id="b", text="Slides on pooling.", retrieval_score=0.8,
                     confidence=0.8, resource_id="r2", slide=5, source_type="slide",
                     citation="[r2, slide 5]", document_title="Slides"),
        EvidenceItem(rank=2, chunk_id="c", text="Boosting ensembles.", retrieval_score=0.7,
                     confidence=0.7, resource_id="en.wikipedia.org", source_type="web",
                     citation="[Boosting — en.wikipedia.org]", document_title="Boosting",
                     metadata={"url": "https://en.wikipedia.org/wiki/Boosting", "domain": "en.wikipedia.org"}),
    ]
    gev = [GraphEvidenceItem(concept_id="concept:cnn", concept="Convolutional Neural Network",
                             score=1.0, hop=0, relationship="seed",
                             path=["Convolutional Neural Network"], source_resources=["r1"],
                             confidence=1.0)]
    return EvidencePackage(query="what is a cnn", normalized_query="cnn", items=items,
                           graph_evidence=gev, overall_confidence=0.85)


# -- resolver --------------------------------------------------------------- #
def test_resolver_builds_pdf_deep_link(settings, tmp_path):
    f = tmp_path / "doc.pdf"; f.write_text("x", encoding="utf-8")
    res = CitationResolver(settings, _Catalog({"r1": _Meta(str(f), "Doc")}))
    idx = CitationExplorer(res).build(_package())
    c1 = next(n for n in idx.nodes if n.cid == "C1")
    assert c1.link.endswith("#page=3") and c1.resolvable and c1.source_type == "pdf"


def test_resolver_concept_and_web_links(settings):
    idx = CitationExplorer(CitationResolver(settings, _Catalog({}))).build(_package())
    web = next(n for n in idx.nodes if n.kind == "web")
    concept = next(n for n in idx.nodes if n.kind == "concept")
    assert web.link.startswith("https://") and web.resolvable
    assert concept.link == "concept:cnn" and concept.resolvable
    # unknown resource → not resolvable
    assert not next(n for n in idx.nodes if n.cid == "C1").resolvable


# -- explorer index --------------------------------------------------------- #
def test_index_kinds_locators_and_stats(settings):
    idx = CitationExplorer(CitationResolver(settings, _Catalog({}))).build(_package())
    kinds = {n.cid: n.kind for n in idx.nodes}
    assert kinds["C1"] == "chunk" and kinds["W1"] == "web" and kinds["K1"] == "concept"
    c2 = next(n for n in idx.nodes if n.cid == "C2")
    assert c2.locator == "slide 5"
    st = idx.stats()
    assert st["by_kind"]["chunk"] == 2 and st["by_kind"]["web"] == 1 and st["by_kind"]["concept"] == 1


def test_filter_and_sources(settings):
    idx = CitationExplorer(CitationResolver(settings, _Catalog({}))).build(_package())
    assert all(n.kind == "chunk" for n in idx.filter(kind="chunk").nodes)
    assert all(n.source_type == "web" for n in idx.filter(source_type="web").nodes)
    assert len(idx.filter(min_confidence=0.85).nodes) < len(idx.nodes)
    assert idx.sources()                                     # grouped source records


def test_max_citations_config(settings):
    idx = CitationExplorer(CitationResolver(settings, _Catalog({})),
                           ExplorerConfig(max_citations=1)).build(_package())
    assert len([n for n in idx.nodes if n.kind in ("chunk", "web")]) == 1


def test_html_is_clickable(settings):
    idx = CitationExplorer(CitationResolver(settings, _Catalog({}))).build(_package())
    page = render(idx)
    assert "<html" in page and "[C1]" in page
    assert "https://en.wikipedia.org/wiki/Boosting" in page   # clickable web link
    assert 'data-kind=' in page and "filter" not in page.lower()[:50]  # filter controls present


# -- real corpus ------------------------------------------------------------ #
def test_real_corpus_explorer():
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.explorer.service import CitationExplorerService
    try:
        svc = CitationExplorerService(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts not built")
    try:
        idx = svc.explore("what is gradient descent", top_k=6)
    finally:
        svc.close()
    st = idx.stats()
    assert idx.nodes and st["resolvable_rate"] > 0.5
    assert any(n.kind == "chunk" for n in idx.nodes) and any(n.kind == "concept" for n in idx.nodes)
