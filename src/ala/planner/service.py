"""StudyPlannerService — wire the planner over the Student Model + concept graph."""

from __future__ import annotations

from pathlib import Path

from ala.planner.models import PlannerConfig, StudyGoal, StudyPlan
from ala.planner.scheduler import StudyPlanner


class StudyPlannerService:
    def __init__(self, settings, *, student_model=None, graph=None,
                 config: PlannerConfig | None = None) -> None:
        self.settings = settings
        self.config = config or PlannerConfig.from_settings(settings)
        self._owns_sm = student_model is None
        if student_model is None:
            from ala.student.model import StudentModel
            student_model = StudentModel(settings)
        self.sm = student_model
        self.graph = graph if graph is not None else self._load_graph(settings)
        self.planner = StudyPlanner(self.graph, self.sm, self.config)

    @staticmethod
    def _load_graph(settings):
        from ala.graph.store import GraphStore
        store = GraphStore(settings.abspath((settings.graph or {}).get(
            "location", "data/graph/concept_graph.db")))
        return store.load() if store.exists() else None

    def plan(self, student_id: str, goal: StudyGoal) -> StudyPlan:
        return self.planner.plan(student_id, goal)

    def export_html(self, student_id: str, goal: StudyGoal, path: str | Path) -> Path:
        from ala.planner.html import render
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        plan = self.plan(student_id, goal)
        p.write_text(render(plan, student_id), encoding="utf-8")
        return p

    def close(self) -> None:
        if self._owns_sm:
            self.sm.close()
