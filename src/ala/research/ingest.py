"""IncrementalIngestor — grow the Knowledge Base through the EXISTING pipeline.

A single new file is pushed through the same components every other resource uses:
ingestion (DIR + metadata + catalog) → parent-child chunking → embedding (same
model as the index) → Qdrant upsert → BM25 add → concept-graph link. Nothing is
rebuilt from scratch and no pipeline is duplicated. Returns per-stage timings and
the new ``resource_id`` so the caller can confirm it is immediately searchable.

Stores are injected (DI) so the same code path serves production (real stores) and
the benchmark/tests (isolated stores) without mutating the live index.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from ala.config.settings import Settings
from ala.ingestion.context import ResourceClassification
from ala.ingestion.pipeline import IngestionPipeline
from ala.retrieval.bm25.index import BM25Index
from ala.retrieval.chunking.service import ChunkingService
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.embedding.pipeline import EmbeddingService
from ala.retrieval.vectorstore.payload import build_payload


@dataclass
class IngestOutcome:
    resource_id: str
    n_children: int
    timings_ms: dict
    total_ms: float
    ok: bool


class IncrementalIngestor:
    def __init__(self, settings: Settings, *, pipeline: IngestionPipeline,
                 chunking: ChunkingService, embedding: EmbeddingService,
                 vector_indexer=None, bm25_index: BM25Index | None = None,
                 bm25_path: str | Path | None = None, graph_store=None,
                 embedder=None, chunk_store: ChunkStore | None = None) -> None:
        self.settings = settings
        self.pipeline = pipeline
        self.chunking = chunking
        self.embedding = embedding
        self.vector_indexer = vector_indexer
        self.bm25_index = bm25_index
        self.bm25_path = Path(bm25_path) if bm25_path else None
        self.graph_store = graph_store
        self.embedder = embedder
        self.chunk_store = chunk_store or ChunkStore(settings.derived_path)

    # ------------------------------------------------------------------ #
    def ingest(self, path: str | Path, classification: ResourceClassification) -> IngestOutcome:
        t: dict = {}
        t0 = time.perf_counter()
        with _timer(t, "ingest"):
            res = self.pipeline.ingest_path(path, classification)
        if not res.ok or res.resource is None:
            return IngestOutcome("", 0, t, round((time.perf_counter() - t0) * 1000, 1), False)
        return self.ingest_resource(res.resource, _timings=t, _t0=t0)

    def ingest_resource(self, resource, *, _timings: dict | None = None,
                        _t0: float | None = None) -> IngestOutcome:
        """Index an already-built + committed LearningResource (chunk → embed →
        Qdrant → BM25 → graph). Shared by ``ingest`` and the Video/Vision adapters
        so no downstream logic is duplicated."""
        t = _timings if _timings is not None else {}
        t0 = _t0 if _t0 is not None else time.perf_counter()
        rid = resource.metadata.resource_id

        with _timer(t, "chunk"):
            chunkset = self.chunking.chunk_resource(resource)
        with _timer(t, "embed"):
            self.embedding.embed_resource(rid, incremental=False)
        if self.vector_indexer is not None:
            with _timer(t, "qdrant"):
                self.vector_indexer.index_resource(rid)
        if self.bm25_index is not None:
            with _timer(t, "bm25"):
                self._update_bm25(rid)
        if self.graph_store is not None:
            with _timer(t, "graph"):
                self._update_graph(resource)

        total = round((time.perf_counter() - t0) * 1000, 1)
        return IngestOutcome(rid, len(chunkset.children), t, total, True)

    # ------------------------------------------------------------------ #
    def _update_bm25(self, rid: str) -> None:
        metas = {m.chunk_id: m for m in self.chunk_store.load_meta(rid, "child")}
        texts = self.chunk_store.load_text(rid, "child")
        for cid, meta in metas.items():
            text = texts.get(cid, "")
            if text.strip():
                self.bm25_index.add(cid, text, payload=build_payload(meta))
        if self.bm25_path is not None:
            self.bm25_index.save(self.bm25_path)

    def _update_graph(self, resource) -> None:
        """Link the new resource into the concept graph without a full rebuild."""
        from ala.graph.builder import GraphBuilder, _tokens
        from ala.graph.concepts import ConceptExtractor
        from ala.graph.graph import ConceptGraph
        from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType

        meta = resource.metadata
        rid = meta.resource_id
        graph = self.graph_store.load() if self.graph_store.exists() else ConceptGraph()
        builder = GraphBuilder(self.settings, self.embedder)
        builder._structural(graph, meta)                     # course⊃module⊃resource⊃topic

        text = " ".join(self.chunk_store.load_text(rid, "child").values())[:30000] or meta.title
        concepts = ConceptExtractor(builder._lexicon, self.embedder).extract({rid: text})
        title_tokens = set(_tokens(meta.title))
        rnode = f"resource:{rid}"
        for c in concepts:
            if not graph.has_node(c.concept_id):             # add new concept, never clobber existing
                graph.add_node(GraphNode(c.concept_id, NodeType.CONCEPT.value, c.canonical,
                                         c.node_attrs()))
            strong = bool(set(_tokens(c.canonical)) & title_tokens)
            graph.add_edge(GraphEdge(c.concept_id, rnode,
                                     EdgeType.APPEARS_IN.value if strong else EdgeType.MENTIONED_IN.value,
                                     provenance=[rid], confidence=c.confidence))
        self.graph_store.save(graph)

    # ------------------------------------------------------------------ #
    @classmethod
    def from_settings(cls, settings: Settings, *, vector_store=None,
                      registry=None) -> "IncrementalIngestor":
        from ala.graph.store import GraphStore
        from ala.registry.registry import ResourceRegistry
        from ala.retrieval.embedding.factory import get_embedder
        from ala.retrieval.search.config import BM25FileConfig, RetrievalConfig
        from ala.retrieval.vectorstore.factory import get_vector_store
        from ala.retrieval.vectorstore.indexer import VectorIndexer

        reg = registry or ResourceRegistry.from_settings(settings)
        pipeline = IngestionPipeline.default(settings)
        cfg = RetrievalConfig.from_settings(settings)
        embedder = get_embedder(cfg.embedding_model)
        vs = vector_store or get_vector_store(settings, dim=embedder.dim)
        embedding = EmbeddingService(settings, embedder=embedder, registry=reg, vector_store=None)
        indexer = VectorIndexer(settings, vs, cfg.embedding_model, registry=reg)
        bm25_path = Path(settings.abspath(BM25FileConfig.from_settings(settings).location))
        bm25 = BM25Index.load(bm25_path) if (bm25_path / "index.pkl").is_file() else BM25Index()
        graph_loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
        return cls(settings, pipeline=pipeline, chunking=ChunkingService(settings, reg),
                   embedding=embedding, vector_indexer=indexer, bm25_index=bm25,
                   bm25_path=bm25_path, graph_store=GraphStore(settings.abspath(graph_loc)),
                   embedder=embedder)


class _timer:
    def __init__(self, store: dict, key: str) -> None:
        self.store, self.key = store, key

    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.store[self.key] = round((time.perf_counter() - self.t0) * 1000, 1)
