"""EvidenceService — wire the EvidenceBuilder from settings.

Bundles the hybrid retriever, chunk-text resolver, and catalog (for document
titles) into a ready builder, and owns their handles (Qdrant + SQLite) so callers
just ``close()``.
"""

from __future__ import annotations

from ala.catalog.repository import KnowledgeCatalog
from ala.config.settings import Settings
from ala.retrieval.evidence.builder import EvidenceBuilder
from ala.retrieval.evidence.models import EvidencePackage
from ala.retrieval.search.factory import build_retrievers
from ala.retrieval.search.textresolver import ChunkTextResolver


class EvidenceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.retrievers = build_retrievers(settings)
        self.catalog = KnowledgeCatalog.from_settings(settings)
        self.builder = EvidenceBuilder(
            self.retrievers.hybrid, ChunkTextResolver(settings), self.catalog, "hybrid"
        )

    def build(self, query: str, *, top_k: int = 8, filters: dict | None = None) -> EvidencePackage:
        return self.builder.build(query, top_k=top_k, filters=filters)

    def close(self) -> None:
        self.retrievers.close()
        self.catalog.close()

    def __enter__(self) -> "EvidenceService":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
