"""Vector-store factory — resolve config to a concrete VectorStore."""

from __future__ import annotations

from ala.config.settings import Settings
from ala.retrieval.vectorstore.base import VectorStore
from ala.retrieval.vectorstore.config import VectorStoreConfig
from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore


def get_vector_store(settings: Settings, *, dim: int | None = None,
                     config: VectorStoreConfig | None = None,
                     collection: str | None = None) -> VectorStore:
    config = config or VectorStoreConfig.from_settings(settings)
    if config.provider != "qdrant":
        raise ValueError(f"unsupported vector store provider '{config.provider}' (only 'qdrant')")
    store = QdrantVectorStore(
        location=config.resolved_location(settings),
        collection=collection or config.collection,
        distance=config.distance,
        dim=dim,
    )
    if dim is not None:
        store.ensure_collection(dim)
    return store
