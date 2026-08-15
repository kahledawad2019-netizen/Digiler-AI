"""Persisted embedding records + per-(resource, model) manifest.

Stores the four things the milestone requires alongside each vector: embedding
model, version, dimension, and timestamp — plus the chunk/content linkage needed
for incremental re-embedding and provenance.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ala.core.clock import utcnow_iso

_Strict = ConfigDict(extra="forbid")


class EmbeddingRecord(BaseModel):
    model_config = _Strict
    chunk_id: str
    resource_id: str
    vector: list[float]
    model_id: str
    version: str
    dim: int
    content_hash: str            # sha256 of the embedded text (incremental key)
    created_at: str = Field(default_factory=utcnow_iso)


class EmbeddingManifest(BaseModel):
    model_config = _Strict
    resource_id: str
    model_id: str
    version: str
    dim: int
    count: int = 0
    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
