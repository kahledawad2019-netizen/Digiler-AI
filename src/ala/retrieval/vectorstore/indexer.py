"""VectorIndexer — populate Qdrant from stored embeddings + chunk metadata.

Reads the persisted per-model vectors (EmbeddingStore) and their chunk metadata
(ChunkStore), builds payloads, and upserts into the vector store — then advances
each resource's ``vector_status`` via the Registry. This is the incremental,
idempotent bridge from the Embedding stage to Qdrant.
"""

from __future__ import annotations

import logging

from ala.config.settings import Settings
from ala.core.enums import StageStatus
from ala.registry.registry import ResourceRegistry
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.embedding.store import EmbeddingStore
from ala.retrieval.vectorstore.base import VectorPoint, VectorStore
from ala.retrieval.vectorstore.payload import build_payload

log = logging.getLogger("ala.retrieval.vectorstore.indexer")


class VectorIndexer:
    def __init__(
        self,
        settings: Settings,
        vector_store: VectorStore,
        model_id: str,
        chunk_store: ChunkStore | None = None,
        embedding_store: EmbeddingStore | None = None,
        registry: ResourceRegistry | None = None,
    ) -> None:
        self.settings = settings
        self.vector_store = vector_store
        self.model_id = model_id
        self.chunk_store = chunk_store or ChunkStore(settings.derived_path)
        self.embedding_store = embedding_store or EmbeddingStore(settings.derived_path)
        self.registry = registry

    def index_resource(self, resource_id: str, *, commit: bool = True) -> int:
        vectors = self.embedding_store.load_vectors(resource_id, self.model_id)
        if not vectors:
            return 0
        metas = {m.chunk_id: m for m in self.chunk_store.load_meta(resource_id, "child")}
        points = [
            VectorPoint(chunk_id=cid, vector=vec, payload=build_payload(metas[cid]))
            for cid, vec in vectors if cid in metas
        ]
        written = self.vector_store.upsert(points)
        if commit and self.registry is not None:
            self.registry.set_status(resource_id, vector_status=StageStatus.DONE)
        log.info("Indexed %s -> %d vectors into Qdrant", resource_id, written)
        return written

    def index_all(self) -> dict[str, int]:
        """Index every resource that has embeddings for this model."""
        out: dict[str, int] = {}
        derived = self.settings.derived_path
        for manifest in sorted(derived.glob(f"*/embeddings/{self.model_id}.manifest.json")):
            resource_id = manifest.parent.parent.name
            out[resource_id] = self.index_resource(resource_id)
        return out
