"""Stage 14 — Research Mode tests.

Unit tests (confidence, source ranking, dedup, merge, parser, search) use synthetic
inputs; the incremental-ingestion and full-controller tests run the real pipeline
offline (local provider + isolated index) when the corpus artifacts are present.
No network is used — the web providers are seams, exercised only via the offline
LocalCacheProvider.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ala.config.settings import load_settings
from ala.rag.models import ContextChunk, GraphRAGAnswer, ReasoningContext
from ala.research.confidence import ConfidenceEstimator
from ala.research.merge import ResearchEvidenceMerger
from ala.research.models import ResearchConfig, ScoredSource, WebDocument, WebResult
from ala.research.parser import WebDocumentParser
from ala.research.search import DisabledProvider, LocalCacheProvider, WebSearchAdapter
from ala.research.sources import SourceQualityEvaluator
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage


def _pkg(semantic: float, bm25: float, n=5) -> EvidencePackage:
    items = [EvidenceItem(rank=i, chunk_id=f"c{i}", text="t", retrieval_score=0.5,
                          semantic_similarity=semantic, bm25_score=bm25,
                          confidence=0.8, resource_id="dl1") for i in range(n)]
    return EvidencePackage(query="q", normalized_query="q", items=items, overall_confidence=0.8)


def _ctx(res="dl1", n=5):
    ctx = ReasoningContext(question="q")
    ctx.chunks = [ContextChunk(cid=f"C{i}", text="t", citation="[dl1]", resource_id=res,
                               source_type="pdf", confidence=0.8, tokens=5) for i in range(n)]
    return ctx


def _ans():
    return GraphRAGAnswer(question="q", answer="a [C1]", grounding={"grounding_ratio": 1.0})


# -- confidence ------------------------------------------------------------- #
def test_confidence_high_when_strong_retrieval():
    rep = ConfidenceEstimator().estimate(_pkg(0.92, 25.0), _ctx(), _ans())
    assert not rep.needs_research and rep.level == "high"


def test_confidence_low_triggers_research():
    # weak semantic + weak BM25 + scattered resources → low confidence
    ctx = ReasoningContext(question="q")
    ctx.chunks = [ContextChunk(cid=f"C{i}", text="t", citation="[r]", resource_id=f"r{i}",
                               source_type="pdf", confidence=0.4, tokens=5) for i in range(3)]
    rep = ConfidenceEstimator().estimate(_pkg(0.45, 3.0, n=3), ctx, _ans())
    assert rep.needs_research and rep.level in ("low", "medium")


# -- source evaluator ------------------------------------------------------- #
def test_source_authority_ranking():
    ev = SourceQualityEvaluator()
    arxiv = ev.score(WebResult("Paper", "https://arxiv.org/abs/1", "deep learning"))
    spam = ev.score(WebResult("Buy", "https://x.biz/p", "buy now cheap crypto giveaway"))
    assert arxiv.trust > 0.6 > spam.trust
    assert spam.spam > 0.0


def test_duplicate_detection_and_select():
    ev = SourceQualityEvaluator(ResearchConfig(min_source_trust=0.3, top_sources=3))
    results = [
        WebResult("A", "https://arxiv.org/abs/1", "paper"),
        WebResult("A dup", "https://arxiv.org/abs/1?utm=x", "paper"),      # duplicate url
        WebResult("B", "https://docs.python.org/3/", "documentation"),
    ]
    ranked = ev.evaluate(results)
    assert sum(1 for s in ranked if s.score.duplicate) == 1
    selected = ev.select(results)
    assert all(not s.score.duplicate for s in selected)


# -- merge ------------------------------------------------------------------ #
def test_merge_keeps_web_and_kb_with_provenance():
    kb = EvidencePackage(query="what is boosting", normalized_query="boosting",
                         items=[EvidenceItem(rank=0, chunk_id="c", text="kb text about boosting",
                                             retrieval_score=0.6, confidence=0.6, resource_id="dl1",
                                             citation="[dl1]")])
    doc = WebDocument(url="https://en.wikipedia.org/wiki/Boosting", title="Boosting",
                      domain="en.wikipedia.org", text="Boosting combines weak learners " * 20)
    src = ScoredSource(WebResult("Boosting", doc.url, provider="local"),
                       SourceQualityEvaluator().score(WebResult("Boosting", doc.url)))
    merged = ResearchEvidenceMerger().merge(kb, [(src, doc)], "what is boosting")
    web = [it for it in merged.items if it.source_type == "web"]
    assert web and web[0].metadata["url"] == doc.url          # provenance preserved
    assert all(it.citation for it in merged.items)            # every item cited
    assert merged.stats["n_kb_items"] == 1 and merged.stats["n_web_items"] >= 1


# -- parser + search -------------------------------------------------------- #
def test_parser_reads_local_html(tmp_path):
    f = tmp_path / "page.html"
    f.write_text("<html><head><title>Gradient Descent</title></head><body><main>"
                 "<p>Gradient descent minimises a loss function by following the negative "
                 "gradient. It is used to train neural networks and many models.</p>"
                 "</main></body></html>", encoding="utf-8")
    r = WebResult("Gradient Descent", f.as_uri(), raw={"path": str(f)})
    doc = WebDocumentParser().fetch(r)
    assert doc and "gradient descent" in doc.text.lower()
    saved = WebDocumentParser().save(doc, tmp_path / "out")
    assert saved.suffix == ".md" and saved.is_file()


def test_disabled_and_local_providers(tmp_path):
    assert WebSearchAdapter(DisabledProvider()).search("x") == []
    (tmp_path / "gd.md").write_text("# Gradient descent\n\ngradient descent optimiser loss",
                                    encoding="utf-8")
    res = LocalCacheProvider(tmp_path).search("gradient descent", k=3)
    assert res and "gradient" in (res[0].snippet + res[0].title).lower()


# -- incremental ingestion (real pipeline, isolated index) ------------------ #
def test_incremental_ingestion_real(tmp_path):
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    from ala.ingestion.context import ResourceClassification
    from ala.ingestion.pipeline import IngestionPipeline
    from ala.core.enums import DocType, Role
    from ala.registry.registry import ResourceRegistry
    from ala.retrieval.bm25.index import BM25Index
    from ala.retrieval.chunking.service import ChunkingService
    from ala.retrieval.chunking.store import ChunkStore
    from ala.retrieval.embedding.factory import get_embedder
    from ala.retrieval.embedding.pipeline import EmbeddingService
    from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore
    from ala.retrieval.vectorstore.indexer import VectorIndexer
    from ala.research.ingest import IncrementalIngestor

    stg = settings.model_copy(update={"paths": settings.paths.model_copy(update={
        "derived_dir": str(tmp_path / "derived"), "raw_dir": str(tmp_path / "raw"),
        "catalog_db": str(tmp_path / "catalog.db")})})
    doc = tmp_path / "note.md"
    doc.write_text("# Support Vector Machines\n\nA support vector machine finds the maximum "
                   "margin hyperplane separating classes using kernels for non-linear data.\n",
                   encoding="utf-8")
    reg = ResourceRegistry.from_settings(stg)
    embedder = get_embedder("hashing")               # fast + offline for the test
    vs = QdrantVectorStore(":memory:", "t_incr"); vs.ensure_collection(embedder.dim)
    ing = IncrementalIngestor(
        stg, pipeline=IngestionPipeline.default(stg), chunking=ChunkingService(stg, reg),
        embedding=EmbeddingService(stg, embedder=embedder, registry=reg, vector_store=None),
        vector_indexer=VectorIndexer(stg, vs, "hashing", registry=reg),
        bm25_index=BM25Index(), bm25_path=tmp_path / "bm25",
        graph_store=GraphStore(tmp_path / "graph.db"), embedder=embedder,
        chunk_store=ChunkStore(stg.derived_path))
    try:
        out = ing.ingest(doc, ResourceClassification(track="research", course="web", module="web",
                         title="Support Vector Machines", doc_type=DocType.WEB, role=Role.REFERENCE))
        assert out.ok and out.n_children >= 1
        hits = ing.bm25_index.search("support vector machine margin hyperplane", top_k=5)
        assert hits                                  # immediately searchable
        assert set(out.timings_ms) >= {"ingest", "chunk", "embed", "qdrant", "bm25", "graph"}
    finally:
        vs.close(); reg.close()


# -- full controller flow (offline, local provider, no ingest) -------------- #
def test_controller_research_flow_offline(tmp_path):
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.rag.pipeline import GraphRAGService
    from ala.research.controller import ResearchModeController
    from ala.research.session import ResearchSessionLog

    (tmp_path / "gb.md").write_text(
        "# Gradient boosting\n\nGradient boosting builds an ensemble of decision trees, each "
        "fitting the residual errors of the previous ones, to improve prediction accuracy.",
        encoding="utf-8")
    # force research; local file sources have no domain authority → accept low trust
    cfg = ResearchConfig(provider="local", confidence_threshold=1.0, min_source_trust=0.0)
    try:
        graphrag = GraphRAGService(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts not built")
    ctrl = ResearchModeController(
        settings, graphrag, search=WebSearchAdapter(LocalCacheProvider(tmp_path), cfg),
        session=ResearchSessionLog(tmp_path / "sessions.jsonl"), config=cfg)
    try:
        res = ctrl.research("what is gradient boosting", approve=None, top_k=6)   # no save
    finally:
        ctrl.close()
    assert res.used_web and res.sources          # web path exercised offline
    assert res.answer and not res.ingested       # answered, nothing saved (no approval)
    assert ResearchSessionLog(tmp_path / "sessions.jsonl").all()   # session logged
