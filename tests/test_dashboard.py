"""Stage 19 — Learning Analytics Dashboard tests."""

from __future__ import annotations

from ala.config.settings import load_settings
from ala.dashboard import charts
from ala.dashboard.builder import DashboardBuilder
from ala.dashboard.html import render
from ala.dashboard.models import DashboardConfig
from ala.dashboard.recommend import RecommendationEngine
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.student.model import StudentModel
from ala.student.models import EventType, StudentConfig
from ala.student.store import StudentStore


def _graph() -> ConceptGraph:
    g = ConceptGraph()
    g.add_node(GraphNode("concept:cnn", NodeType.CONCEPT.value, "Convolutional Neural Network",
                         {"domain": "deep-learning", "frequency": 50}))
    g.add_node(GraphNode("concept:sql", NodeType.CONCEPT.value, "SQL Join",
                         {"domain": "databases", "frequency": 30}))
    g.add_node(GraphNode("resource:r1", NodeType.RESOURCE.value, "CNN Lecture", {"resource_id": "r1"}))
    g.add_edge(GraphEdge("concept:cnn", "resource:r1", EdgeType.APPEARS_IN.value))
    g.add_edge(GraphEdge("concept:cnn", "concept:sql", EdgeType.RELATED_TO.value))
    return g


def _model(tmp_path) -> StudentModel:
    return StudentModel(load_settings(None), store=StudentStore(tmp_path / "s.db"),
                        config=StudentConfig())


# -- recommendation engine -------------------------------------------------- #
def test_recommendations_target_weak_with_resources(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u")
        for _ in range(3):
            m.record_quiz("u", ["concept:cnn"], correct=False, difficulty=0.6)
        recs = RecommendationEngine(g, m).recommend("u")
        cnn = next(r for r in recs if r.concept_id == "concept:cnn")
        assert cnn.kind in ("review", "practice")
        assert any(res["resource_id"] == "r1" for res in cnn.resources)
    finally:
        m.close()


# -- builder ---------------------------------------------------------------- #
def test_builder_assembles_analytics(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u", explanation_style="example-driven")
        for _ in range(3):
            m.record_quiz("u", ["concept:cnn"], correct=False, difficulty=0.6)
        for _ in range(3):
            m.record_quiz("u", ["concept:sql"], correct=True, difficulty=0.5)
        m.record_exposure("u", EventType.LESSON.value, ["concept:sql"], ref="r1")
        data = DashboardBuilder(m, g, None, DashboardConfig()).build("u")
        assert data.summary["n_tracked"] == 2
        assert len(data.heatmap) == 2 and data.domain_mastery
        assert data.time_spent["total_minutes"] > 0
        assert data.completion["concepts_seen"] == 2 and data.completion["resources_completed"] == 1
        assert data.confidence_evolution and data.recommendations
    finally:
        m.close()


# -- charts + html ---------------------------------------------------------- #
def test_charts_emit_svg():
    assert charts.hbars([("a", 0.5), ("b", 0.9)]).startswith("<svg")
    assert "<path" in charts.line([0.1, 0.4, 0.8])
    assert charts.heatmap([{"concept": "x", "domain": "d", "mastery": 0.3}]).startswith("<svg")
    assert "%" in charts.donut(0.42)
    assert charts.mastery_color(0.2) != charts.mastery_color(0.9)


def test_html_dashboard_is_self_contained(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u", name="Ada")
        m.record_quiz("u", ["concept:cnn"], correct=False)
        page = render(DashboardBuilder(m, g).build("u"))
        assert "<html" in page and "Ada" in page
        assert 'class="tab"' in page and "<svg" in page
        assert "http" not in page.split("</head>")[0].replace("http-equiv", "")  # no external assets
    finally:
        m.close()
