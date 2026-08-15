"""The callable tool catalog — safe utilities + wrappers over existing controllers.

Service-backed tools reuse the Stage-22 Tool registry (one retrieval path, one
ingestion path, …). Added here: ``calculator`` and ``python`` (sandboxed),
``pdf``, ``video`` and ``calendar``. Each is a ``FunctionSpec`` with a JSON schema.
"""

from __future__ import annotations

from ala.functions.calendar import plan_to_ics
from ala.functions.models import FunctionSpec
from ala.functions.safety import SafeCalculator, SafePython


def build_functions(services, *, python_timeout: float = 2.0,
                    allow_knowledge_update: bool = True) -> list[FunctionSpec]:
    from ala.agents.tools import build_tools
    at = build_tools(services)
    calc, py = SafeCalculator(), SafePython(python_timeout)

    def calculator(expression: str) -> dict:
        return {"expression": expression, "value": calc.eval(expression)}

    def python(code: str) -> dict:
        return py.run(code)

    def search(question: str, top_k: int = 5) -> dict:
        r = at["retrieval_qa"].run(question=question, top_k=top_k)
        return {"answer": r["answer"], "grounding": r["grounding"], "citations": r["citations"]}

    def knowledge_update(source: str, title: str = "") -> dict:
        if not allow_knowledge_update:
            raise PermissionError("knowledge_update is disabled by policy")
        return at["knowledge_update"].run(source=source, title=title or None)

    def planner(student_id: str = "default", goal: str = "master my weak concepts",
                days: int = 14, minutes: int = 60) -> dict:
        return at["plan"].run(student_id=student_id, goal=goal, days=days, minutes=minutes)

    def quiz(concept: str, student_id: str = "default") -> dict:
        q = at["quiz_gen"].run(concept=concept, student_id=student_id)
        return {"question": q["question"], "difficulty": q["difficulty"], "source": q.get("source")}

    def web_search(query: str) -> dict:
        return at["web_search"].run(query=query)

    def pdf(path: str, max_chars: int = 2000) -> dict:
        from pypdf import PdfReader
        reader = PdfReader(path)
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return {"n_pages": len(reader.pages), "chars": len(text), "text": text[: int(max_chars)]}

    def video(source: str) -> dict:
        from ala.video.adapter import VideoAdapter
        t = VideoAdapter().transcribe(source)
        return {"title": t.info.title, "n_cues": len(t.cues), "duration": round(t.duration, 1),
                "preview": t.text()[:400]}

    def calendar(student_id: str = "default", days: int = 14, minutes: int = 60) -> dict:
        from ala.planner.models import StudyGoal
        plan = services.planner.plan(student_id, StudyGoal(deadline_days=days, minutes_per_day=minutes))
        return {"ics": plan_to_ics(plan), "n_days": len(plan.days), "total_minutes": plan.total_minutes}

    S = lambda t, req=False, d="": {"type": t, "required": req, "description": d}
    return [
        FunctionSpec("calculator", "Evaluate a safe arithmetic expression.", calculator,
                     {"expression": S("string", True, "e.g. '2 * (3 + 4) ** 2'")}),
        FunctionSpec("python", "Run a short Python snippet in a sandbox (set `result`).", python,
                     {"code": S("string", True, "restricted: no imports/IO; assign `result`")}),
        FunctionSpec("search", "Answer a question from the Knowledge Base (grounded + cited).", search,
                     {"question": S("string", True), "top_k": S("integer", False)}),
        FunctionSpec("planner", "Generate an adaptive study plan.", planner,
                     {"student_id": S("string"), "goal": S("string"), "days": S("integer"),
                      "minutes": S("integer")}),
        FunctionSpec("quiz", "Generate an adaptive quiz question for a concept.", quiz,
                     {"concept": S("string", True), "student_id": S("string")}),
        FunctionSpec("web_search", "Search + rank web sources.", web_search,
                     {"query": S("string", True)}),
        FunctionSpec("pdf", "Extract text from a local PDF file.", pdf,
                     {"path": S("string", True), "max_chars": S("integer")}),
        FunctionSpec("video", "Transcribe a video / caption file into timestamped cues.", video,
                     {"source": S("string", True, "URL / .mp4 / .vtt")}),
        FunctionSpec("calendar", "Export a study plan as an iCalendar (.ics).", calendar,
                     {"student_id": S("string"), "days": S("integer"), "minutes": S("integer")}),
        FunctionSpec("knowledge_update", "Grow the Knowledge Base from a source (gated).",
                     knowledge_update, {"source": S("string", True), "title": S("string")},
                     safe=False, mutating=True),
    ]
