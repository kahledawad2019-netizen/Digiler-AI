"""Stage 18 — Student Model tests."""

from __future__ import annotations

from ala.config.settings import load_settings
from ala.graph.graph import ConceptGraph
from ala.graph.models import EdgeType, GraphEdge, GraphNode, NodeType
from ala.student.mastery import MasteryModel
from ala.student.model import StudentModel
from ala.student.models import ConceptMastery, EventType, StudentConfig, StudentProfile
from ala.student.personalize import PersonalizedRetriever
from ala.student.store import StudentStore
from ala.retrieval.types import RetrievalResult


def _model(tmp_path) -> StudentModel:
    settings = load_settings(None)
    return StudentModel(settings, store=StudentStore(tmp_path / "s.db"), config=StudentConfig())


# -- store ------------------------------------------------------------------ #
def test_store_profile_mastery_events_roundtrip(tmp_path):
    store = StudentStore(tmp_path / "s.db")
    store.upsert_profile(StudentProfile("u1", name="Ada", level="advanced", goals=["exam"]))
    got = store.get_profile("u1")
    assert got.name == "Ada" and got.level == "advanced" and got.goals == ["exam"]
    store.set_mastery("u1", ConceptMastery("concept:cnn", 0.55, 2, 1))
    assert store.get_mastery("u1", "concept:cnn").mastery == 0.55
    assert store.all_mastery("u1")[0].concept_id == "concept:cnn"
    store.close()


# -- mastery model ---------------------------------------------------------- #
def test_mastery_rises_on_correct_falls_on_incorrect():
    mm = MasteryModel(StudentConfig())
    cm = ConceptMastery("c")
    start = cm.mastery
    mm.update(cm, kind=EventType.QUIZ.value, score=1.0, difficulty=0.6)
    assert cm.mastery > start and cm.correct == 1
    cm2 = ConceptMastery("c")
    mm.update(cm2, kind=EventType.QUIZ.value, score=0.0, difficulty=0.6)
    assert cm2.mastery < start


def test_exposure_nudges_up_and_thresholds():
    mm = MasteryModel(StudentConfig(weak_threshold=0.4, strong_threshold=0.7))
    cm = ConceptMastery("c", mastery=0.35)
    mm.update(cm, kind=EventType.READING.value, score=None)
    assert cm.mastery > 0.35
    assert mm.is_weak(ConceptMastery("c", 0.3)) and mm.is_strong(ConceptMastery("c", 0.8))


# -- student model ---------------------------------------------------------- #
def test_record_quiz_and_weak_strong(tmp_path):
    m = _model(tmp_path)
    try:
        m.get_or_create("u", explanation_style="example-driven")
        for _ in range(3):
            m.record_quiz("u", ["concept:hard"], correct=False, difficulty=0.6)
        for _ in range(3):
            m.record_quiz("u", ["concept:easy"], correct=True, difficulty=0.6)
        weak = {c.concept_id for c in m.weak_concepts("u")}
        strong = {c.concept_id for c in m.strong_concepts("u")}
        assert "concept:hard" in weak and "concept:easy" in strong
        s = m.mastery_summary("u")
        assert s["n_tracked"] == 2 and s["n_events"] == 6
    finally:
        m.close()


# -- personalized retriever ------------------------------------------------- #
class StubHybrid:
    def __init__(self, rows):
        self.rows = rows

    def retrieve(self, query, *, top_k=10, filters=None):
        return [RetrievalResult(chunk_id=c, score=s, rank=i, source="hybrid",
                                payload={"resource_id": rid, "language": "en"},
                                component_scores={"rrf": s})
                for i, (c, rid, s) in enumerate(self.rows[:top_k])]


def test_personalized_retriever_boosts_weak_resources(tmp_path):
    g = ConceptGraph()
    g.add_node(GraphNode("concept:weak", NodeType.CONCEPT.value, "Weak", {}))
    g.add_node(GraphNode("resource:r_weak", NodeType.RESOURCE.value, "rw", {"resource_id": "r_weak"}))
    g.add_edge(GraphEdge("concept:weak", "resource:r_weak", EdgeType.APPEARS_IN.value))

    m = _model(tmp_path)
    try:
        m.get_or_create("u")
        for _ in range(3):
            m.record_quiz("u", ["concept:weak"], correct=False, difficulty=0.6)   # → weak
        # base ranks r_other above r_weak
        base = StubHybrid([("a", "r_other", 0.9), ("b", "r_weak", 0.5)])
        pers = PersonalizedRetriever(base, m, "u", g, StudentConfig(weak_weight=0.6, candidate_k=10))
        assert "r_weak" in pers.weak_resources
        ranked = pers.retrieve("q", top_k=2)
        assert ranked[0].payload["resource_id"] == "r_weak"          # promoted for remediation
        assert ranked[0].component_scores["student"] > 0
    finally:
        m.close()


# -- analytics -------------------------------------------------------------- #
def test_analytics_shape(tmp_path):
    from ala.student.analytics import compute_analytics
    m = _model(tmp_path)
    try:
        m.get_or_create("u")
        m.record_quiz("u", ["concept:a"], correct=True)
        m.record_quiz("u", ["concept:b"], correct=False)
        a = compute_analytics(m, "u")
        assert "mastery_histogram" in a and len(a["mastery_histogram"]["counts"]) == 5
        assert a["progress"].get("quiz") == 2 and "summary" in a
    finally:
        m.close()
