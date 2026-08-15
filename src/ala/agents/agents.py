"""The agent roster — each agent is a thin role over the shared tools.

No agent implements retrieval, ingestion or scoring itself; it composes the tools
(which wrap the existing services). Every agent returns an ``AgentResult``.
"""

from __future__ import annotations

from ala.agents.models import AgentRequest, AgentResult, AgentRole, Tool


class Agent:
    role: str = "agent"
    name: str = "Agent"
    description: str = ""

    def __init__(self, tools: dict[str, Tool]) -> None:
        self.tools = tools

    def run(self, request: AgentRequest) -> AgentResult:      # pragma: no cover - abstract
        raise NotImplementedError

    def _result(self, output: str, **kw) -> AgentResult:
        return AgentResult(agent=self.name, role=self.role, output=output, **kw)


class TutorAgent(Agent):
    role, name = AgentRole.TUTOR.value, "Tutor"
    description = "Explains concepts with grounded, cited answers (GraphRAG)."

    def run(self, request: AgentRequest) -> AgentResult:
        r = self.tools["retrieval_qa"].run(question=request.text)
        style = None
        if request.concept:
            style = self.tools["adaptive_policy"].run(
                student_id=request.student_id, concept=request.concept).get("explanation_style")
        prefix = f"({style} explanation) " if style else ""
        return self._result(prefix + r["answer"], citations=r["citations"],
                            data={"grounding": r["grounding"], "confidence": r["confidence"],
                                  "explanation_style": style},
                            tools_used=["retrieval_qa"] + (["adaptive_policy"] if style else []))


class QuizAgent(Agent):
    role, name = AgentRole.QUIZ.value, "Quiz"
    description = "Generates an adaptive quiz question from evidence (RL difficulty)."

    def run(self, request: AgentRequest) -> AgentResult:
        concept = request.concept or request.text
        q = self.tools["quiz_gen"].run(concept=concept, student_id=request.student_id)
        pol = self.tools["adaptive_policy"].run(student_id=request.student_id, concept=concept)
        return self._result(f"[{q['difficulty']}] {q['question']}",
                            data={**q, "concept": concept, "choice": pol["choice"]},
                            tools_used=["adaptive_policy", "evidence", "quiz_gen"])


class EvaluatorAgent(Agent):
    role, name = AgentRole.EVALUATOR.value, "Evaluator"
    description = "Grades a learner's answer + records the outcome (mastery + RL)."

    def run(self, request: AgentRequest) -> AgentResult:
        key_terms = request.meta.get("key_terms", [])
        g = self.tools["grade"].run(student_answer=request.text, key_terms=key_terms)
        concept = request.concept or request.meta.get("concept")
        choice = request.meta.get("choice")
        if concept and choice:
            rec = self.tools["record_outcome"].run(
                student_id=request.student_id, concept=concept, choice=choice,
                correct=g["correct"], response_time=request.meta.get("response_time", 10.0))
            g["recorded"] = rec
        return self._result(g["feedback"], data=g,
                            tools_used=["grade"] + (["record_outcome"] if concept and choice else []))


class PlannerAgent(Agent):
    role, name = AgentRole.PLANNER.value, "Planner"
    description = "Builds an adaptive study plan (Study Planner)."

    def run(self, request: AgentRequest) -> AgentResult:
        days = int(request.meta.get("days", 14))
        minutes = int(request.meta.get("minutes", 60))
        r = self.tools["plan"].run(student_id=request.student_id,
                                   goal=request.text or "master my weak concepts",
                                   days=days, minutes=minutes)
        return self._result(
            f"Study plan: {r['n_days']} days, {r['total_minutes']} min total.",
            data=r, tools_used=["plan"])


class ResearchAgent(Agent):
    role, name = AgentRole.RESEARCH.value, "Research"
    description = "Answers with confidence-gated web research (Research Mode)."

    def run(self, request: AgentRequest) -> AgentResult:
        r = self.tools["research"].run(question=request.text)
        return self._result(r["answer"],
                            data={"used_web": r["used_web"], "confidence": r["confidence"],
                                  "ingested": r["ingested"]},
                            citations=[{"label": s.get("domain", ""), "url": s.get("url", "")}
                                       for s in r["sources"]],
                            tools_used=["research"])


class WebResearchAgent(Agent):
    role, name = AgentRole.WEB_RESEARCH.value, "WebResearch"
    description = "Searches + ranks web sources (Web Search)."

    def run(self, request: AgentRequest) -> AgentResult:
        r = self.tools["web_search"].run(query=request.text)
        top = ", ".join(f"{s['domain']} ({s['trust']:.2f})" for s in r["sources"][:3]) or "(none)"
        return self._result(f"Top sources: {top}", data=r, tools_used=["web_search"])


class KnowledgeCuratorAgent(Agent):
    role, name = AgentRole.CURATOR.value, "KnowledgeCurator"
    description = "Grows the Knowledge Base from a source (Incremental Ingestor)."

    def run(self, request: AgentRequest) -> AgentResult:
        source = request.meta.get("source", request.text)
        r = self.tools["knowledge_update"].run(source=source, title=request.meta.get("title"))
        msg = (f"Added resource {r['resource_id']} ({r['n_children']} chunks)."
               if r["ok"] else "Could not ingest the source.")
        return self._result(msg, data=r, tools_used=["knowledge_update"])
