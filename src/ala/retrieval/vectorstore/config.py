"""Vector-store configuration (parsed from platform.yaml `retrieval.vector_store`)."""

from __future__ import annotations

from pydantic import BaseModel

from ala.config.settings import Settings


class VectorStoreConfig(BaseModel):
    provider: str = "qdrant"
    location: str = "data/qdrant"       # filesystem path (local mode) or ":memory:"
    collection: str = "ala_chunks"
    distance: str = "cosine"            # cosine | dot | euclid
    batch_size: int = 256

    @classmethod
    def from_settings(cls, settings: Settings) -> "VectorStoreConfig":
        return cls(**(settings.retrieval or {}).get("vector_store", {}))

    def resolved_location(self, settings: Settings) -> str:
        """Absolute path for local mode; ``:memory:`` passed through unchanged."""
        if self.location == ":memory:":
            return ":memory:"
        return str(settings.abspath(self.location))
