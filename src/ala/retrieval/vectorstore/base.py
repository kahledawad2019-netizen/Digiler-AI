"""VectorStore interface + value types.

The contract every backend implements. Search returns typed ``SearchHit``s
(never raw driver objects), so retrieval code stays backend-agnostic and the LLM
path never sees a database row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class VectorPoint:
    """One vector to index: the chunk id, its embedding, and its payload."""

    chunk_id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    payload: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    collection: str
    distance: str

    def ensure_collection(self, dim: int, *, recreate: bool = False) -> None:
        """Create the collection (idempotent). ``recreate`` drops it first."""
        ...

    def upsert(self, points: list[VectorPoint], *, batch_size: int | None = None) -> int:
        """Insert/update points (idempotent by chunk_id). Returns count written."""
        ...

    def delete(self, chunk_ids: list[str]) -> int: ...

    def delete_by_resource(self, resource_id: str) -> int: ...

    def search(self, vector: list[float], *, top_k: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchHit]:
        """Nearest neighbours, optionally constrained by a payload filter."""
        ...

    def count(self) -> int: ...

    def health(self) -> dict[str, Any]: ...

    def stats(self) -> dict[str, Any]: ...

    def close(self) -> None: ...
