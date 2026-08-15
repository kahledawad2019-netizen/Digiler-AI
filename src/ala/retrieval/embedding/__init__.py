"""Stage 4 — Embedding Pipeline.

A model-agnostic embedding layer: one ``Embedder`` interface, several backends
(a dependency-free hashing embedder that always works, plus sentence-transformer
models e5-small / bge-m3 / MiniLM), versioned persistence, a content-hash cache,
incremental batch embedding, and benchmark/visualization utilities.

Retrieval code (Stage 5+) depends only on ``Embedder`` and ``EmbeddingStore`` —
switching models never touches it (Dependency Inversion).
"""

from ala.retrieval.embedding.base import Embedder, EmbeddingResult
from ala.retrieval.embedding.config import EmbeddingConfig, MODEL_SPECS
from ala.retrieval.embedding.factory import available_models, get_embedder
from ala.retrieval.embedding.hashing import HashingEmbedder
from ala.retrieval.embedding.models import EmbeddingManifest, EmbeddingRecord
from ala.retrieval.embedding.cache import EmbeddingCache
from ala.retrieval.embedding.store import EmbeddingStore
from ala.retrieval.embedding.pipeline import EmbeddingService

__all__ = [
    "Embedder",
    "EmbeddingResult",
    "EmbeddingConfig",
    "MODEL_SPECS",
    "get_embedder",
    "available_models",
    "HashingEmbedder",
    "EmbeddingRecord",
    "EmbeddingManifest",
    "EmbeddingCache",
    "EmbeddingStore",
    "EmbeddingService",
]
