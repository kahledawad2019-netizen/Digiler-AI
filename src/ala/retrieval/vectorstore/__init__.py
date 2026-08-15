"""Stage 5 — Vector Store layer (Qdrant).

A provider-agnostic ``VectorStore`` interface with a production ``QdrantVectorStore``
backend (local mode = zero-infra, ``:memory:`` for tests). Retrieval code depends
only on the interface, so the backend is swappable (Dependency Inversion).
"""

from ala.retrieval.vectorstore.base import SearchHit, VectorPoint, VectorStore
from ala.retrieval.vectorstore.config import VectorStoreConfig
from ala.retrieval.vectorstore.factory import get_vector_store
from ala.retrieval.vectorstore.indexer import VectorIndexer
from ala.retrieval.vectorstore.payload import build_payload, point_id
from ala.retrieval.vectorstore.qdrant_store import QdrantVectorStore

__all__ = [
    "VectorStore",
    "VectorPoint",
    "SearchHit",
    "VectorStoreConfig",
    "QdrantVectorStore",
    "get_vector_store",
    "VectorIndexer",
    "build_payload",
    "point_id",
]
