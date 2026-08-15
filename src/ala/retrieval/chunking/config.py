"""Chunking configuration (parsed from platform.yaml `retrieval.chunking`)."""

from __future__ import annotations

from pydantic import BaseModel

from ala.config.settings import Settings


class ChunkingConfig(BaseModel):
    parent_target_tokens: int = 512
    child_target_tokens: int = 180
    child_overlap_tokens: int = 40
    min_chunk_tokens: int = 8

    @classmethod
    def from_settings(cls, settings: Settings) -> "ChunkingConfig":
        block = (settings.retrieval or {}).get("chunking", {})
        return cls(**block)
