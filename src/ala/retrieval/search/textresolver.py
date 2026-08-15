"""ChunkTextResolver — resolve chunk text on demand (for reranking / evidence).

Retrieval carries payloads, not full text (to stay light). When the cross-encoder
reranker or the Evidence Package needs the text, this resolves it from the
ChunkStore, caching per resource to avoid repeated reads.
"""

from __future__ import annotations

from ala.config.settings import Settings
from ala.retrieval.chunking.store import ChunkStore
from ala.retrieval.search.types import RetrievalResult


class ChunkTextResolver:
    def __init__(self, settings: Settings) -> None:
        self.chunk_store = ChunkStore(settings.derived_path)
        self._cache: dict[str, dict[str, str]] = {}

    def text(self, chunk_id: str) -> str | None:
        resource_id = chunk_id.split("::")[0]
        if resource_id not in self._cache:
            self._cache[resource_id] = self.chunk_store.load_text(resource_id, "child")
        return self._cache[resource_id].get(chunk_id)

    def attach(self, results: list[RetrievalResult]) -> list[RetrievalResult]:
        for r in results:
            if r.text is None:
                r.text = self.text(r.chunk_id)
        return results
