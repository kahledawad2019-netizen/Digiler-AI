"""Stage 20 — Study Planner tests."""

from __future__ import annotations

from ala.config.settings import load_settings
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.planner.models import ActivityType, PlannerConfig, StudyGoal
from ala.planner.scheduler import StudyPlanner
from ala.student.model import StudentModel
from ala.student.models import StudentConfig
from ala.student.store import StudentStore


def _res(g, rid, doc_type, course, module, title):
    g.add_node(GraphNode(f"resource:{rid}", NodeType.RESOURCE.value, title,
                         {"resource_id": rid, "doc_type": doc_type, "course": course, "module": module}))


def _graph() -> ConceptGraph:
    g = ConceptGraph()
    g.add_node(GraphNode("concept:early", NodeType.CONCEPT.value, "Foundations",
                         {"domain": "ml", "frequency": 40}))
    g.add_node(GraphNode("concept:late", NodeType.CONCEPT.value, "Advanced Topic",
                         {"domain": "ml", "frequency": 20}))
    _res(g, "r_read", "lesson_page", "c1", "w01", "Intro lesson")
    _res(g, "r_vid", "video", "c1", "w01", "Intro video")
    _res(g, "r_prac", "assessment", "c1", "w01", "Practice set")
    _res(g, "r_late", "textbook", "c1", "w03", "Advanced chapter")
    for r in ("r_read", "r_vid", "r_prac"):
        g.add_edge(GraphEdge("concept:early", f"resource:{r}", EdgeType.APPEARS_IN.value))
    g.add_edge(GraphEdge("concept:late", "resource:r_late", EdgeType.APPEARS_IN.value))
    return g


def _model(tmp_path) -> StudentModel:
    return StudentModel(load_settings(None), store=StudentStore(tmp_path / "s.db"),
                        config=StudentConfig())


# -- resource bucketing ----------------------------------------------------- #
def test_resource_buckets_by_doctype(tmp_path):
    planner = StudyPlanner(_graph(), _model(tmp_path))
    try:
        res = planner._resources("concept:early")
        assert res["read"] and res["watch"] and res["practice"]
        assert planner._week("concept:early") == 1 and planner._week("concept:late") == 3
    finally:
        planner.sm.close()


# -- plan generation -------------------------------------------------------- #
def test_plan_budget_deadline_and_ordering(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u")
        for _ in range(3):
            m.record_quiz("u", ["concept:early"], correct=False, difficulty=0.6)
            m.record_quiz("u", ["concept:late"], correct=False, difficulty=0.6)
        plan = StudyPlanner(g, m, PlannerConfig()).plan(
            "u", StudyGoal(deadline_days=6, minutes_per_day=60))
        # ordering: early (week 1) before late (week 3)
        assert [c["concept"] for c in plan.concepts] == ["Foundations", "Advanced Topic"]
        # budget + deadline respected
        assert plan.stats["max_day_minutes"] <= 60 and plan.stats["fits_deadline"]
        assert len(plan.days) <= 6
        # weak concepts → practice + revision present; video → watch present
        types = {a.type for d in plan.days for a in d.activities}
        assert ActivityType.PRACTICE.value in types and ActivityType.REVISION.value in types
        assert ActivityType.WATCH.value in types and ActivityType.QUIZ.value in types
    finally:
        m.close()


def test_weak_concept_gets_more_time(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u")
        for _ in range(3):                                   # early → weak
            m.record_quiz("u", ["concept:early"], correct=False, difficulty=0.6)
        for _ in range(3):                                   # late → strong
            m.record_quiz("u", ["concept:late"], correct=True, difficulty=0.6)
        plan = StudyPlanner(g, m, PlannerConfig()).plan("u", StudyGoal(concept_ids=[
            "concept:early", "concept:late"], deadline_days=8, minutes_per_day=90))
        acts = [a for d in plan.days for a in d.activities]
        early_min = sum(a.minutes for a in acts if a.concept_id == "concept:early")
        late_min = sum(a.minutes for a in acts if a.concept_id == "concept:late")
        assert early_min > late_min                          # weak concept gets more time
        assert any(a.type == "revision" and a.concept_id == "concept:early" for a in acts)
        assert not any(a.type == "revision" and a.concept_id == "concept:late" for a in acts)
    finally:
        m.close()


def test_explicit_goal_and_stats(tmp_path):
    g, m = _graph(), _model(tmp_path)
    try:
        m.get_or_create("u")
        plan = StudyPlanner(g, m).plan("u", StudyGoal(concept_ids=["concept:early"],
                                                      deadline_days=3, minutes_per_day=60))
        assert plan.stats["n_concepts"] == 1 and plan.total_minutes > 0
        assert plan.stats["by_activity"].get("quiz", 0) >= 1
    finally:
        m.close()
