"""ChunkingService — connects chunking to the platform (ingestion output → chunks).

Consumes a ``LearningResource`` (the DIR source, produced by ingestion and saved
under ``derived/``), produces + persists the ChunkSet, and updates the resource's
retrieval metadata (`parent_chunk_ids`, `child_chunk_ids`, `chunk_count`) and
processing status (`chunked`) via the Registry — keeping the catalog authoritative.
"""

from __future__ import annotations

import logging

from ala.config.settings import Settings
from ala.core.enums import ProcessingStatus, StageStatus
from ala.fabric.learning_resource import LearningResource
from ala.registry.registry import ResourceRegistry
from ala.retrieval.chunking.chunker import ParentChildChunker
from ala.retrieval.chunking.config import ChunkingConfig
from ala.retrieval.chunking.models import ChunkSet
from ala.retrieval.chunking.store import ChunkStore

log = logging.getLogger("ala.retrieval.chunking")


class ChunkingService:
    def __init__(
        self,
        settings: Settings,
        registry: ResourceRegistry | None = None,
        chunker: ParentChildChunker | None = None,
        store: ChunkStore | None = None,
    ) -> None:
        self.settings = settings
        self.registry = registry
        self.chunker = chunker or ParentChildChunker(ChunkingConfig.from_settings(settings))
        self.store = store or ChunkStore(settings.derived_path)

    def chunk_resource(
        self, resource: LearningResource, *, persist: bool = True, commit: bool = True
    ) -> ChunkSet:
        chunkset = self.chunker.chunk(resource)
        if persist:
            self.store.save(chunkset)

        meta = resource.metadata
        meta.retrieval.parent_chunk_ids = chunkset.parent_ids
        meta.retrieval.child_chunk_ids = chunkset.child_ids
        meta.retrieval.chunk_count = len(chunkset.children)
        if meta.status.processing_status != ProcessingStatus.FAILED.value:
            meta.status.processing_status = ProcessingStatus.CHUNKED.value
        meta.add_processing_step(
            "chunking", status=StageStatus.DONE, tool="ParentChildChunker",
            notes=f"{len(chunkset.parents)} parents / {len(chunkset.children)} children",
        )
        if commit and self.registry is not None:
            self.registry.commit(meta)
        log.info("Chunked %s -> %d parents / %d children",
                 meta.resource_id, len(chunkset.parents), len(chunkset.children))
        return chunkset

    def chunk_from_derived(self, resource_id: str, *, commit: bool = True) -> ChunkSet:
        resource = LearningResource.load(self.settings.derived_path, resource_id)
        return self.chunk_resource(resource, commit=commit)
