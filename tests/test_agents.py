"""Stage 22 — AI Agents tests (stub tools for unit, real corpus for integration)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ala.agents.agents import EvaluatorAgent, QuizAgent, TutorAgent
from ala.agents.coordinator import Coordinator, Crew
from ala.agents.models import AgentRequest, AgentRole, Tool
from ala.agents import quizgen
from ala.config.settings import load_settings


@dataclass
class _Item:
    text: str
    citation: str = "[src]"
    resource_id: str = "r1"


# -- coordinator routing ---------------------------------------------------- #
def test_routing_intents():
    c = Coordinator({})
    assert c.route("quiz me on cnns") == AgentRole.QUIZ.value
    assert c.route("make a study plan") == AgentRole.PLANNER.value
    assert c.route("research the latest models") == AgentRole.RESEARCH.value
    assert c.route("search the web for x") == AgentRole.WEB_RESEARCH.value
    assert c.route("ingest this into knowledge") == AgentRole.CURATOR.value
    assert c.route("what is gradient descent") == AgentRole.TUTOR.value    # default


# -- quiz generation + grading ---------------------------------------------- #
def test_quizgen_and_grade():
    items = [_Item("Gradient descent minimises a loss function by following the negative gradient.")]
    q = quizgen.generate_quiz("gradient descent", items, difficulty="medium")
    assert "gradient descent" in q["question"].lower() and q["key_terms"]
    good = quizgen.grade(q["answer_key"], q["key_terms"])
    bad = quizgen.grade("i like pizza", q["key_terms"])
    assert good["correct"] and good["score"] >= 0.4
    assert not bad["correct"]


# -- tools ------------------------------------------------------------------ #
def test_tool_run():
    t = Tool("echo", "", lambda x: {"y": x * 2})
    assert t.run(x=3) == {"y": 6}


def _stub_tools():
    return {
        "retrieval_qa": Tool("retrieval_qa", "", lambda question, top_k=8: {
            "answer": f"Answer about {question}", "grounding": 1.0, "citations": [{"cid": "C1"}],
            "confidence": 0.8, "package": None, "context": None}),
        "adaptive_policy": Tool("adaptive_policy", "", lambda student_id, concept: {
            "difficulty": "medium", "difficulty_value": 0.5, "explanation_style": "concise",
            "choice": {"decision": "difficulty", "action_index": 2, "action": "medium",
                       "context": [0.3, 0.5, 0.0, 1.0], "difficulty": 0.5}}),
        "evidence": Tool("evidence", "", lambda query, top_k=6: {
            "items": [_Item("Backpropagation trains a neural network via the chain rule of gradients.")],
            "graph_evidence": []}),
        "quiz_gen": Tool("quiz_gen", "", lambda concept, student_id="default": {
            **quizgen.generate_quiz(concept, [_Item(
                "Backpropagation trains a neural network via the chain rule of gradients.")], "medium"),
            "explanation_style": "concise"}),
        "grade": Tool("grade", "", lambda student_answer, key_terms, threshold=None:
                      quizgen.grade(student_answer, key_terms)),
        "record_outcome": Tool("record_outcome", "", lambda student_id, concept, choice, correct,
                               response_time=10.0: {"reward": 0.5 if correct else -0.1,
                                                    "mastery_before": 0.3, "mastery_after": 0.4,
                                                    "difficulty": "medium"}),
    }


# -- agents (stubbed tools) ------------------------------------------------- #
def test_tutor_agent_uses_retrieval_only():
    r = TutorAgent(_stub_tools()).run(AgentRequest(text="what is backprop", concept="concept:bp"))
    assert r.role == "tutor" and "backprop" in r.output.lower()
    assert r.data["grounding"] == 1.0 and "retrieval_qa" in r.tools_used


def test_quiz_then_evaluator_records():
    tools = _stub_tools()
    quiz = QuizAgent(tools).run(AgentRequest(text="Backpropagation", concept="concept:bp",
                                             student_id="u"))
    assert quiz.data["key_terms"] and quiz.data["choice"]
    ev = EvaluatorAgent(tools).run(AgentRequest(
        text=quiz.data["answer_key"], concept="concept:bp", student_id="u",
        meta={"key_terms": quiz.data["key_terms"], "concept": "concept:bp",
              "choice": quiz.data["choice"]}))
    assert ev.data["correct"] and ev.data["recorded"]["mastery_after"] == 0.4
    assert "record_outcome" in ev.tools_used


def test_crew_study_session_stubbed():
    tools = _stub_tools()
    tools["plan"] = Tool("plan", "", lambda student_id="default", goal="", days=14, minutes=60:
                         {"plan": {}, "n_days": 5, "total_minutes": 300})
    agents = {
        AgentRole.TUTOR.value: TutorAgent(tools), AgentRole.QUIZ.value: QuizAgent(tools),
        AgentRole.EVALUATOR.value: EvaluatorAgent(tools),
        AgentRole.PLANNER.value: __import__("ala.agents.agents", fromlist=["PlannerAgent"]).PlannerAgent(tools),
    }
    ss = Crew(agents).study_session(
        "u", "Backpropagation",
        answer="backpropagation trains a neural network via the chain rule of gradients")
    assert len(ss["transcript"]) == 4 and ss["correct"]


# -- real corpus ------------------------------------------------------------ #
def test_real_corpus_agents():
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.agents.service import AgentService
    try:
        svc = AgentService(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts not built")
    try:
        r = svc.ask("what is a convolutional neural network")
        assert r.role == "tutor" and r.output and r.data.get("grounding") is not None
        assert svc.coordinator.route("quiz me on x") == "quiz"
    finally:
        svc.close()
