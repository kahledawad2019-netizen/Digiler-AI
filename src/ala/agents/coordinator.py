"""Coordinator + Crew — route a request to an agent, or run a multi-agent flow.

The Coordinator classifies intent (keyword-based, deterministic) and dispatches to
the right agent. The Crew runs collaborative flows — e.g. a study session where the
Tutor explains, the Quiz Agent asks, the Evaluator grades (advancing mastery + the
RL policy) and the Planner recommends next steps — all reusing the shared services.
"""

from __future__ import annotations

from ala.agents.models import AgentRequest, AgentResult, AgentRole

# Intent keywords, checked in order (first match wins). Kept deterministic + explainable.
# Keywords are substring-matched against the lowercased request, so avoid short/ambiguous
# tokens and words that are substrings of common terms (e.g. "reference" ⊂ "preferences").
_INTENT = [
    (("quiz", "test me", "ask me", "practice question", "question me", "mcq",
      "multiple choice", "true or false", "assessment", "exam question", "give me questions"),
     AgentRole.QUIZ),
    (("study plan", "learning plan", "revision plan", "study schedule", "study roadmap",
      "study timeline", "plan my", "plan for", "make a plan", "create a plan", "build a plan",
      "roadmap", "road map", "schedule", "timeline", "curriculum", "learning path",
      "prepare for", "day plan", "week plan", "weekly plan", "daily plan"),
     AgentRole.PLANNER),
    (("save this", "ingest", "add to knowledge", "add to the knowledge base", "curate",
      "remember this page", "save to knowledge"), AgentRole.CURATOR),
    (("search the web", "web sources", "find online", "look online", "on the web",
      "web search", "google", "from the internet", "online sources"), AgentRole.WEB_RESEARCH),
    (("find resources", "resources", "papers", "literature", "documentation", "articles",
      "reading list", "citations", "research", "latest", "recent advances", "look up",
      "find out about", "read about", "sources on"), AgentRole.RESEARCH),
]


class Coordinator:
    def __init__(self, agents: dict) -> None:
        self.agents = agents

    def route(self, text: str) -> str:
        low = (text or "").lower()
        for keywords, role in _INTENT:
            if any(k in low for k in keywords):
                return role.value
        return AgentRole.TUTOR.value

    def handle(self, request: AgentRequest) -> AgentResult:
        role = self.route(request.text)
        result = self.agents[role].run(request)
        result.data["routed_to"] = role
        return result


class Crew:
    def __init__(self, agents: dict) -> None:
        self.agents = agents
        self.coordinator = Coordinator(agents)

    def study_session(self, student_id: str, concept: str, *, answer: str | None = None) -> dict:
        """Tutor → Quiz → Evaluator → Planner, collaborating over the shared services."""
        tutor = self.agents[AgentRole.TUTOR.value].run(
            AgentRequest(text=f"explain {concept}", student_id=student_id, concept=concept))
        quiz = self.agents[AgentRole.QUIZ.value].run(
            AgentRequest(text=concept, student_id=student_id, concept=concept))
        student_answer = answer if answer is not None else tutor.output   # demo: a good answer
        evaluator = self.agents[AgentRole.EVALUATOR.value].run(AgentRequest(
            text=student_answer, student_id=student_id, concept=concept,
            meta={"key_terms": quiz.data.get("key_terms", []), "concept": concept,
                  "choice": quiz.data.get("choice")}))
        planner = self.agents[AgentRole.PLANNER.value].run(
            AgentRequest(text="master my weak concepts", student_id=student_id))
        return {
            "concept": concept,
            "transcript": [r.to_dict() for r in (tutor, quiz, evaluator, planner)],
            "correct": evaluator.data.get("correct"),
            "mastery_after": evaluator.data.get("recorded", {}).get("mastery_after"),
        }
