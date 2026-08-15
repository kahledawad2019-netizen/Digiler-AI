"""QdrantVectorStore — the production vector backend.

Uses qdrant-client in **local mode** (a filesystem path) so the platform stays
zero-infra and local-first — no server process — with ``:memory:`` for tests.
Implements the full ``VectorStore`` contract: collection management, batched
upsert with vector validation, id/resource deletion, metadata-filtered search,
count, health, and stats.

qdrant-client is imported lazily so importing this module never requires the
dependency until a store is actually constructed.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from ala.core.exceptions import AlaError
from ala.retrieval.vectorstore.base import SearchHit, VectorPoint
from ala.retrieval.vectorstore.payload import point_id

log = logging.getLogger("ala.retrieval.vectorstore")

_DISTANCE = {"cosine": "Cosine", "dot": "Dot", "euclid": "Euclid"}


class VectorStoreError(AlaError):
    """A vector-store operation failed."""


class QdrantVectorStore:
    def __init__(self, location: str, collection: str, distance: str = "cosine",
                 dim: int | None = None) -> None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:  # pragma: no cover - env-dependent
            raise VectorStoreError('qdrant-client not installed: pip install "qdrant-client>=1.10"') from exc

        self.location = location
        self.collection = collection
        self.distance = distance
        self._dim = dim
        # ":memory:" (tests) · an http(s):// URL (production server, shared/concurrent
        # so the API can read while ingestion writes) · else a local path (single process).
        if location == ":memory:":
            self._client = QdrantClient(location=":memory:")
        elif location.startswith(("http://", "https://")):
            self._client = QdrantClient(url=location)
        else:
            self._client = QdrantClient(path=location)

    # -- collection management ------------------------------------------- #
    def ensure_collection(self, dim: int, *, recreate: bool = False) -> None:
        from qdrant_client import models as qm

        self._dim = dim
        exists = self._client.collection_exists(self.collection)
        if recreate and exists:
            self._client.delete_collection(self.collection)
            exists = False
        if not exists:
            self._client.create_collection(
                self.collection,
                vectors_config=qm.VectorParams(
                    size=dim, distance=getattr(qm.Distance, _DISTANCE[self.distance].upper())
                ),
            )
            log.info("Created Qdrant collection '%s' (dim=%d, %s)", self.collection, dim, self.distance)

    # -- writes ----------------------------------------------------------- #
    def upsert(self, points: list[VectorPoint], *, batch_size: int | None = None) -> int:
        from qdrant_client import models as qm

        if not points:
            return 0
        self._validate([p.vector for p in points])
        bs = batch_size or 256
        written = 0
        for start in range(0, len(points), bs):
            batch = points[start:start + bs]
            structs = [
                qm.PointStruct(id=point_id(p.chunk_id), vector=p.vector,
                               payload={**p.payload, "chunk_id": p.chunk_id})
                for p in batch
            ]
            self._client.upsert(self.collection, points=structs)
            written += len(structs)
        return written

    def delete(self, chunk_ids: list[str]) -> int:
        from qdrant_client import models as qm

        if not chunk_ids:
            return 0
        self._client.delete(
            self.collection,
            points_selector=qm.PointIdsList(points=[point_id(c) for c in chunk_ids]),
        )
        return len(chunk_ids)

    def delete_by_resource(self, resource_id: str) -> int:
        from qdrant_client import models as qm

        flt = qm.Filter(must=[qm.FieldCondition(key="resource_id", match=qm.MatchValue(value=resource_id))])
        n = self._client.count(self.collection, count_filter=flt, exact=True).count
        self._client.delete(self.collection, points_selector=qm.FilterSelector(filter=flt))
        return n

    # -- reads ------------------------------------------------------------ #
    def search(self, vector: list[float], *, top_k: int = 10,
               filters: dict[str, Any] | None = None) -> list[SearchHit]:
        self._validate([vector])
        result = self._client.query_points(
            self.collection, query=vector, limit=top_k,
            query_filter=self._build_filter(filters), with_payload=True,
        )
        return [
            SearchHit(chunk_id=p.payload.get("chunk_id", ""), score=float(p.score), payload=p.payload)
            for p in result.points
        ]

    def count(self) -> int:
        return self._client.count(self.collection, exact=True).count

    def health(self) -> dict[str, Any]:
        try:
            info = self._client.get_collection(self.collection)
            return {"ok": True, "collection": self.collection,
                    "status": str(info.status), "points": self.count()}
        except Exception as exc:  # noqa: BLE001 - health must not raise
            return {"ok": False, "collection": self.collection, "error": str(exc)}

    def stats(self) -> dict[str, Any]:
        info = self._client.get_collection(self.collection)
        return {
            "collection": self.collection,
            "points": info.points_count,
            "dim": self._dim,
            "distance": self.distance,
            "status": str(info.status),
            "location": self.location,
        }

    def close(self) -> None:
        self._client.close()

    # -- internals -------------------------------------------------------- #
    def _validate(self, vectors: list[list[float]]) -> None:
        for v in vectors:
            if self._dim is not None and len(v) != self._dim:
                raise VectorStoreError(f"vector dim {len(v)} != collection dim {self._dim}")
            if not all(math.isfinite(x) for x in v):
                raise VectorStoreError("vector contains non-finite values (nan/inf)")

    def _build_filter(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        from qdrant_client import models as qm

        conditions = []
        for key, value in filters.items():
            match = qm.MatchAny(any=list(value)) if isinstance(value, (list, tuple, set)) \
                else qm.MatchValue(value=value)
            conditions.append(qm.FieldCondition(key=key, match=match))
        return qm.Filter(must=conditions)
