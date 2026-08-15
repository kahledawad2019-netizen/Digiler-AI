"""Tools — named wrappers over the EXISTING services (single source of truth).

Every capability an agent uses is one of these tools, and each tool calls exactly
one existing service method (GraphRAG, Research, Planner, RL, Student Model,
Incremental Ingestor). There is therefore one retrieval path, one ingestion path,
etc. — nothing is duplicated. The same registry powers Function Calling (Stage 23).
"""

from __future__ import annotations

from ala.agents.models import Tool


def build_tools(svc) -> dict[str, Tool]:
    """svc is an AgentServices bundle exposing the shared service handles."""

    def retrieval_qa(question: str, top_k: int = 8) -> dict:
        ans, ctx, pkg = svc.graphrag.answer_with_context(question, top_k=top_k)
        return {"answer": ans.answer, "grounding": ans.grounding.get("grounding_ratio"),
                "citations": [c.__dict__ for c in ans.citations],
                "confidence": ans.confidence, "package": pkg, "context": ctx}

    def evidence(query: str, top_k: int = 6) -> dict:
        # Retrieval ONLY — return the evidence package without running the (slow) LLM
        # generator. Consumers like quiz generation need retrieved chunks, not a written
        # answer; calling answer_with_context here forced a full LLM generation per quiz,
        # which exceeded the frontend proxy timeout and reset the socket.
        pkg, _gres = svc.graphrag.pipeline.merger.merge(query, top_k=top_k)
        return {"items": pkg.items, "graph_evidence": pkg.graph_evidence}

    def plan(student_id: str = "default", goal: str = "master my weak concepts",
             days: int = 14, minutes: int = 60) -> dict:
        from ala.planner.models import StudyGoal
        p = svc.planner.plan(student_id, StudyGoal(description=goal, deadline_days=days,
                                                   minutes_per_day=minutes))
        return {"plan": p.to_dict(), "n_days": len(p.days), "total_minutes": p.total_minutes}

    def student_summary(student_id: str = "default") -> dict:
        return {"summary": svc.student_model.mastery_summary(student_id),
                "weak": [c.concept_id for c in svc.student_model.weak_concepts(student_id, k=6)]}

    def adaptive_policy(student_id: str = "default", concept: str = "") -> dict:
        d = svc.rl.choose_difficulty(student_id, concept, explore=False)
        s = svc.rl.choose(student_id, concept, decision="explanation_style", explore=False)
        return {"difficulty": d["action"], "difficulty_value": d.get("difficulty"),
                "explanation_style": s["action"], "choice": d}

    def research(question: str) -> dict:
        r = svc.research.research(question)
        return {"answer": r.answer, "used_web": r.used_web, "confidence": r.confidence.score,
                "sources": r.sources, "ingested": r.ingested}

    def web_search(query: str) -> dict:
        scored = svc.research.evaluator.select(svc.research.search.search(query))
        return {"sources": [{"title": s.result.title, "url": s.result.url,
                             "domain": s.result.domain, "trust": s.score.trust} for s in scored]}

    def knowledge_update(source: str, title: str | None = None) -> dict:
        from ala.core.enums import DocType, Role
        from ala.ingestion.context import ResourceClassification
        outcome = svc.ingestor.ingest(source, ResourceClassification(
            track="research", course="web", module="agent", title=title or "agent source",
            doc_type=DocType.WEB, role=Role.REFERENCE))
        return {"resource_id": outcome.resource_id, "ok": outcome.ok,
                "n_children": outcome.n_children}

    def quiz_gen(concept: str, student_id: str = "default") -> dict:
        from ala.agents import quizgen
        pol = adaptive_policy(student_id, concept)
        ev = evidence(concept, top_k=6)["items"]
        q = quizgen.generate_quiz(concept, ev, difficulty=pol["difficulty"])
        return {**q, "explanation_style": pol["explanation_style"]}

    def grade(student_answer: str, key_terms: list, threshold: float | None = None) -> dict:
        from ala.agents import quizgen
        return quizgen.grade(student_answer, key_terms,
                             threshold=threshold if threshold is not None else svc.grade_threshold)

    def record_outcome(student_id: str, concept: str, choice: dict, correct: bool,
                       response_time: float = 10.0) -> dict:
        it = svc.rl.record_outcome(student_id, concept, choice, correct=correct,
                                   response_time=response_time)
        return {"reward": it.reward, "mastery_before": it.mastery_before,
                "mastery_after": it.mastery_after, "difficulty": it.action}

    defs = [
        ("retrieval_qa", "Answer a question from the Knowledge Base (GraphRAG), grounded + cited.", retrieval_qa),
        ("evidence", "Retrieve cited evidence for a query (GraphRAG).", evidence),
        ("plan", "Generate an adaptive study plan (Study Planner).", plan),
        ("student_summary", "Summarise a learner's mastery + weak concepts (Student Model).", student_summary),
        ("adaptive_policy", "Choose adaptive difficulty + explanation style (RL policy).", adaptive_policy),
        ("research", "Answer with confidence-gated web research (Research Mode).", research),
        ("web_search", "Search + rank web sources (Web Search).", web_search),
        ("knowledge_update", "Grow the Knowledge Base from a source (Incremental Ingestor).", knowledge_update),
        ("quiz_gen", "Generate an adaptive quiz question from evidence.", quiz_gen),
        ("grade", "Grade a learner's answer against the answer key.", grade),
        ("record_outcome", "Record a quiz outcome (advances mastery + updates the RL policy).", record_outcome),
    ]
    return {name: Tool(name, desc, func) for name, desc, func in defs}
