"""Payload schema: what travels alongside each vector in Qdrant.

Qdrant point IDs must be UUIDs or unsigned ints, but our chunk ids are strings
(``<rid>::c00001``), so we map each to a deterministic UUID5 and keep the real
chunk_id in the payload. The payload carries exactly the fields retrieval and the
Evidence Package (Stage 9) need for filtering and citations — no more.
"""

from __future__ import annotations

import uuid

from ala.retrieval.chunking.models import ChunkMetadata

_NAMESPACE = uuid.UUID("6f0c8a2e-1b3d-4e5a-9c7f-1a2b3c4d5e6f")


def point_id(chunk_id: str) -> str:
    """Deterministic UUID for a chunk id (so upserts are idempotent)."""
    return str(uuid.uuid5(_NAMESPACE, chunk_id))


def build_payload(meta: ChunkMetadata) -> dict:
    parts = meta.resource_id.split(".")
    return {
        "chunk_id": meta.chunk_id,
        "resource_id": meta.resource_id,
        "parent_id": meta.parent_id,
        "kind": str(meta.kind),
        "chunk_type": str(meta.chunk_type),
        "language": meta.language,
        "token_count": meta.token_count,
        "section_path": meta.section_path,
        "heading": meta.heading,
        "page": meta.page,
        "page_end": meta.page_end,
        "slide": meta.slide,
        "timestamp": meta.timestamp,
        "topics": meta.topics,
        "keywords": meta.keywords,
        "track": parts[0] if len(parts) > 0 else None,
        "course": parts[1] if len(parts) > 1 else None,
        "module": parts[2] if len(parts) > 2 else None,
        "embedding_model": meta.embedding_model,
        "embedding_version": meta.embedding_version,
    }
