"""CitationExplorerService — wire the explorer over the live pipeline."""

from __future__ import annotations

from pathlib import Path

from ala.explorer.explorer import CitationExplorer
from ala.explorer.models import CitationIndex, ExplorerConfig
from ala.explorer.resolver import CitationResolver
from ala.retrieval.evidence.models import EvidencePackage


class CitationExplorerService:
    """Build citation indexes from GraphRAG output; export HTML/JSON."""

    def __init__(self, settings, config: ExplorerConfig | None = None) -> None:
        from ala.catalog.repository import KnowledgeCatalog
        from ala.rag.pipeline import GraphRAGService

        self.settings = settings
        self.config = config or ExplorerConfig.from_settings(settings)
        self.catalog = KnowledgeCatalog.from_settings(settings)
        self.graphrag = GraphRAGService(settings)
        self.explorer = CitationExplorer(CitationResolver(settings, self.catalog), self.config)

    def explore(self, query: str, *, top_k: int = 8) -> CitationIndex:
        _ans, _ctx, pkg = self.graphrag.answer_with_context(query, top_k=top_k)
        return self.index_of(pkg)

    def index_of(self, pkg: EvidencePackage) -> CitationIndex:
        return self.explorer.build(pkg)

    def export_html(self, query: str, path: str | Path, *, top_k: int = 8) -> Path:
        from ala.explorer.html import render
        index = self.explore(query, top_k=top_k)
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(index, title=f"Citation Explorer — {query}"), encoding="utf-8")
        return p

    def close(self) -> None:
        self.graphrag.close()
        self.catalog.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
