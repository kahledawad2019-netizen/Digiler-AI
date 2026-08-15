"""AgentService — wire the shared services, tools, agents, coordinator and crew.

Builds **one** GraphRAG stack, **one** Student Model, **one** concept graph and
shares them across every agent (Research Mode reuses the same GraphRAG — retrieval
is never duplicated). The Incremental Ingestor (curator) is built lazily since it
loads the embedder/index only when knowledge growth is actually requested.
"""

from __future__ import annotations

from ala.agents.agents import (EvaluatorAgent, KnowledgeCuratorAgent, PlannerAgent,
                               QuizAgent, ResearchAgent, TutorAgent, WebResearchAgent)
from ala.agents.coordinator import Coordinator, Crew
from ala.agents.models import AgentRequest, AgentResult, AgentRole
from ala.agents.tools import build_tools


class AgentServices:
    """Shared service handles the tools wrap (single source of truth per capability)."""

    def __init__(self, settings) -> None:
        from ala.graph.store import GraphStore
        from ala.rag.pipeline import GraphRAGService
        from ala.research.controller import ResearchModeController
        from ala.research.models import ResearchConfig
        from ala.research.search import WebSearchAdapter
        from ala.rl.controller import AdaptiveController
        from ala.planner.scheduler import StudyPlanner
        from ala.student.model import StudentModel

        self.settings = settings
        self.graphrag = GraphRAGService(settings)
        self.student_model = StudentModel(settings)
        self.graph = GraphStore(settings.abspath((settings.graph or {}).get(
            "location", "data/graph/concept_graph.db"))).load()
        self.rl = AdaptiveController(settings, self.student_model, graph=self.graph)
        self.planner = StudyPlanner(self.graph, self.student_model)
        rcfg = ResearchConfig.from_settings(settings)
        self.research = ResearchModeController(
            settings, self.graphrag, search=WebSearchAdapter.from_settings(settings, rcfg),
            config=rcfg)
        self.grade_threshold = float((getattr(settings, "agents", None) or {}).get("grade_threshold", 0.4))
        self._ingestor = None

    @property
    def ingestor(self):
        if self._ingestor is None:
            from ala.research.ingest import IncrementalIngestor
            self._ingestor = IncrementalIngestor.from_settings(self.settings)
        return self._ingestor

    def close(self) -> None:
        self.graphrag.close()            # research shares this handle → closed once here
        self.student_model.close()


class AgentService:
    def __init__(self, settings) -> None:
        self.settings = settings
        self.services = AgentServices(settings)
        self.tools = build_tools(self.services)
        self.agents = {
            AgentRole.TUTOR.value: TutorAgent(self.tools),
            AgentRole.QUIZ.value: QuizAgent(self.tools),
            AgentRole.EVALUATOR.value: EvaluatorAgent(self.tools),
            AgentRole.PLANNER.value: PlannerAgent(self.tools),
            AgentRole.RESEARCH.value: ResearchAgent(self.tools),
            AgentRole.WEB_RESEARCH.value: WebResearchAgent(self.tools),
            AgentRole.CURATOR.value: KnowledgeCuratorAgent(self.tools),
        }
        self.coordinator = Coordinator(self.agents)
        self.crew = Crew(self.agents)

    def ask(self, text: str, *, student_id: str = "default", concept: str | None = None,
            **meta) -> AgentResult:
        return self.coordinator.handle(AgentRequest(text=text, student_id=student_id,
                                                    concept=concept, meta=meta))

    def study_session(self, student_id: str, concept: str, *, answer: str | None = None) -> dict:
        return self.crew.study_session(student_id, concept, answer=answer)

    def close(self) -> None:
        self.services.close()
