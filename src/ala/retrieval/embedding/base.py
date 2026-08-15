"""The Embedder interface and result type.

Every backend implements the same contract, so the rest of the platform is
model-agnostic. Documents and queries have separate methods because some models
(notably multilingual-e5) require different prefixes for each.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class EmbeddingResult:
    """A batch of vectors plus the provenance needed to persist them."""

    model_id: str          # short key, e.g. "e5-small" | "hashing"
    version: str           # exact, reproducible version string
    dim: int
    vectors: list[list[float]]


@runtime_checkable
class Embedder(Protocol):
    model_id: str
    version: str
    dim: int

    def embed_documents(self, texts: list[str], batch_size: int | None = None) -> list[list[float]]:
        """Embed passages/documents (L2-normalized)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query (L2-normalized)."""
        ...
