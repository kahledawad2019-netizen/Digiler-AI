"""DashboardService — wire the dashboard over the Student Model + graph + catalog."""

from __future__ import annotations

from pathlib import Path

from ala.dashboard.builder import DashboardBuilder
from ala.dashboard.models import DashboardConfig, DashboardData


class DashboardService:
    def __init__(self, settings, *, student_model=None, graph=None, catalog=None,
                 config: DashboardConfig | None = None) -> None:
        self.settings = settings
        self.config = config or DashboardConfig.from_settings(settings)
        self._owns_sm = student_model is None
        self._owns_catalog = catalog is None
        if student_model is None:
            from ala.student.model import StudentModel
            student_model = StudentModel(settings)
        self.sm = student_model
        self.graph = graph if graph is not None else self._load_graph(settings)
        if catalog is None:
            from ala.catalog.repository import KnowledgeCatalog
            catalog = KnowledgeCatalog.from_settings(settings)
        self.catalog = catalog
        self.builder = DashboardBuilder(self.sm, self.graph, self.catalog, self.config)

    @staticmethod
    def _load_graph(settings):
        from ala.graph.store import GraphStore
        store = GraphStore(settings.abspath((settings.graph or {}).get(
            "location", "data/graph/concept_graph.db")))
        return store.load() if store.exists() else None

    def build(self, student_id: str) -> DashboardData:
        return self.builder.build(student_id)

    def export_html(self, student_id: str, path: str | Path) -> Path:
        from ala.dashboard.html import render
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render(self.build(student_id)), encoding="utf-8")
        return p

    def close(self) -> None:
        if self._owns_sm:
            self.sm.close()
        if self._owns_catalog:
            self.catalog.close()
