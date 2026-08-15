"""EmbeddingService — embed chunks, cache, persist, and update the catalog.

Connects Stage 4 to the platform: reads a resource's child chunks from the
ChunkStore, embeds them (batched, cache-backed, incremental), persists vectors +
manifest via the EmbeddingStore, stamps each chunk's metadata with the embedding
model/version/dim, and advances the resource's processing status to ``embedded``
through the Registry (catalog stays authoritative).
"""

from __future__ import annotations

import logging

from ala.config.settings import Settings
from ala.core.clock import utcnow_iso
from ala.core.enums import ProcessingStatus, StageStatus
from ala.core.hashing import sha256_text
from ala.registry.registry import ResourceRegistry
from ala.retrieval.chunking.models import ChunkSet
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.embedding.base import Embedder
from ala.retrieval.embedding.cache import EmbeddingCache
from ala.retrieval.embedding.config import EmbeddingConfig
from ala.retrieval.embedding.factory import get_embedder
from ala.retrieval.embedding.models import EmbeddingRecord
from ala.retrieval.embedding.store import EmbeddingStore

log = logging.getLogger("ala.retrieval.embedding")


class EmbeddingService:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder | None = None,
        registry: ResourceRegistry | None = None,
        chunk_store: ChunkStore | None = None,
        embedding_store: EmbeddingStore | None = None,
        config: EmbeddingConfig | None = None,
        vector_store=None,
    ) -> None:
        self.settings = settings
        self.config = config or EmbeddingConfig.from_settings(settings)
        self.embedder = embedder or get_embedder(
            self.config.default_model, device=self.config.device,
            hashing_dim=self.config.hashing_dim,
        )
        self.registry = registry
        self.chunk_store = chunk_store or ChunkStore(settings.derived_path)
        self.embedding_store = embedding_store or EmbeddingStore(settings.derived_path)
        self.vector_store = vector_store        # optional: populate Qdrant directly
        self._cache = (
            EmbeddingCache(settings.derived_path, self.embedder.version)
            if self.config.use_cache else None
        )

    # ------------------------------------------------------------------ #
    def embed_chunkset(self, chunkset: ChunkSet, *, persist: bool = True) -> list[EmbeddingRecord]:
        children = chunkset.children
        texts = [c.text for c in children]
        hashes = [sha256_text(t) for t in texts]

        vectors: list[list[float] | None] = [None] * len(texts)
        todo_idx: list[int] = []
        for i, h in enumerate(hashes):
            cached = self._cache.get(h) if self._cache else None
            if cached is not None:
                vectors[i] = cached
            else:
                todo_idx.append(i)

        if todo_idx:
            fresh = self.embedder.embed_documents(
                [texts[i] for i in todo_idx], batch_size=self.config.batch_size
            )
            for i, vec in zip(todo_idx, fresh):
                vectors[i] = vec
                if self._cache:
                    self._cache.put(hashes[i], vec)

        records = [
            EmbeddingRecord(
                chunk_id=children[i].chunk_id, resource_id=chunkset.resource_id,
                vector=vectors[i], model_id=self.embedder.model_id,
                version=self.embedder.version, dim=self.embedder.dim, content_hash=hashes[i],
            )
            for i in range(len(children))
        ]
        if persist and records:
            self.embedding_store.save(
                chunkset.resource_id, self.embedder.model_id, self.embedder.version,
                self.embedder.dim, records,
            )
            if self._cache:
                self._cache.flush()
        return records

    def embed_resource(self, resource_id: str, *, incremental: bool = True,
                       commit: bool = True) -> list[EmbeddingRecord]:
        chunkset = self.chunk_store.load_chunkset(resource_id)
        if incremental and self._already_embedded(resource_id, len(chunkset.children)):
            log.info("Skip %s (already embedded with %s)", resource_id, self.embedder.version)
            return []

        records = self.embed_chunkset(chunkset)

        # stamp chunk metadata + advance resource status
        for chunk in chunkset.children:
            chunk.metadata.embedding_model = self.embedder.model_id
            chunk.metadata.embedding_version = self.embedder.version
            chunk.metadata.embedding_dim = self.embedder.dim
        self.chunk_store.save(chunkset)

        # Optionally populate the vector store (Qdrant) in the same pass.
        if self.vector_store is not None and records:
            from ala.retrieval.vectorstore.base import VectorPoint
            from ala.retrieval.vectorstore.payload import build_payload

            self.vector_store.ensure_collection(self.embedder.dim)
            self.vector_store.upsert([
                VectorPoint(chunk_id=c.chunk_id, vector=r.vector, payload=build_payload(c.metadata))
                for c, r in zip(chunkset.children, records)
            ])

        if commit and self.registry is not None:
            self.registry.set_status(
                resource_id, processing_status=ProcessingStatus.EMBEDDED,
                embedding_status=StageStatus.DONE, embedder_version=self.embedder.version,
                vector_status=StageStatus.DONE if self.vector_store is not None else None,
            )
        log.info("Embedded %s: %d vectors (%s, dim=%d)",
                 resource_id, len(records), self.embedder.model_id, self.embedder.dim)
        return records

    def embed_all(self, *, incremental: bool = True) -> dict[str, int]:
        """Embed every chunked resource. Iterates on-disk chunk sets, so it is
        model-agnostic: re-running with a different model embeds the same
        resources regardless of their current processing_status."""
        out: dict[str, int] = {}
        for manifest in sorted(self.settings.derived_path.glob("*/chunks/children.meta.jsonl")):
            rid = manifest.parent.parent.name
            out[rid] = len(self.embed_resource(rid, incremental=incremental))
        return out

    # ------------------------------------------------------------------ #
    def _already_embedded(self, resource_id: str, n_children: int) -> bool:
        manifest = self.embedding_store.load_manifest(resource_id, self.embedder.model_id)
        return bool(manifest and manifest.version == self.embedder.version
                    and manifest.count == n_children)
