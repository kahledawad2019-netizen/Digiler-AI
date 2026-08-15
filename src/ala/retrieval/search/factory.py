"""Factory — wire the full hybrid retrieval stack from settings.

Loads the embedder + Qdrant (dense), the persisted BM25 index (lexical), the
optional reranker, and the text resolver into a ready ``HybridRetriever``, and
exposes the single-arm retrievers for evaluation. Returns a ``Retrievers`` bundle
whose ``close()`` releases the Qdrant handle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ala.config.settings import Settings
from ala.retrieval.bm25.index import BM25Index
from ala.retrieval.bm25.retriever import BM25Retriever
from ala.retrieval.embedding.factory import get_embedder
from ala.retrieval.search.config import BM25FileConfig, RetrievalConfig
from ala.retrieval.search.dense import DenseRetriever
from ala.retrieval.search.hybrid import HybridRetriever
from ala.retrieval.search.reranker import CrossEncoderReranker, IdentityReranker
from ala.retrieval.search.textresolver import ChunkTextResolver
from ala.retrieval.vectorstore.factory import get_vector_store


@dataclass
class Retrievers:
    dense: DenseRetriever
    bm25: BM25Retriever
    hybrid: HybridRetriever
    config: RetrievalConfig
    _vector_store: object

    def close(self) -> None:
        self._vector_store.close()


def _model_dim(settings: Settings, model: str) -> int | None:
    import json
    for m in sorted(settings.derived_path.glob(f"*/embeddings/{model}.manifest.json")):
        return json.loads(m.read_text(encoding="utf-8"))["dim"]
    return None


def build_retrievers(settings: Settings, config: RetrievalConfig | None = None) -> Retrievers:
    cfg = config or RetrievalConfig.from_settings(settings)

    dim = _model_dim(settings, cfg.embedding_model)
    embedder = get_embedder(cfg.embedding_model, hashing_dim=dim or 384)
    vector_store = get_vector_store(settings, dim=dim or embedder.dim)
    dense = DenseRetriever(embedder, vector_store)

    bm25_cfg = BM25FileConfig.from_settings(settings)
    bm25_path = Path(settings.abspath(bm25_cfg.location))
    if not (bm25_path / "index.pkl").is_file():
        raise FileNotFoundError(
            f"BM25 index not found at {bm25_path}. Build it first: `ala bm25 build`."
        )
    bm25 = BM25Retriever(BM25Index.load(bm25_path))

    reranker = CrossEncoderReranker(cfg.rerank_model, device="cpu") if cfg.rerank_enabled \
        else IdentityReranker()
    hybrid = HybridRetriever(dense, bm25, cfg, reranker, ChunkTextResolver(settings))
    return Retrievers(dense=dense, bm25=bm25, hybrid=hybrid, config=cfg, _vector_store=vector_store)
