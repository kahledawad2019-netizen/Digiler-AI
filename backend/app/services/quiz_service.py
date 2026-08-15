"""Interactive quiz generation — structured MCQ / True-False / Short-Answer questions.

Grounded in retrieved evidence (retrieval-only, no wasted generation for the context).
When Ollama is reachable, Qwen3 writes varied, cited questions with answers + explanations;
otherwise it degrades to an extractive short-answer question (never a hard failure).
"""

from __future__ import annotations

import json
import logging
import re

from app.deps.services import AlaServices
from app.services import chat_service

log = logging.getLogger("digiler.quiz")
_JSON_ARRAY = re.compile(r"\[.*\]", re.DOTALL)
_VALID_TYPES = {"multiple_choice", "true_false", "short_answer"}


def concept_for_resource(services: AlaServices, resource_id: str) -> str | None:
    g = services.graph
    return next((nb for nb, _e, _d in g.neighbors(f"resource:{resource_id}")
                 if nb.startswith("concept:")), None)


def _evidence(services: AlaServices, query: str, top_k: int = 4):
    pkg = chat_service.retrieve_package(services, query, top_k=top_k)
    lines = []
    for it in pkg.items[:top_k]:
        cid = getattr(it, "citation", "") or getattr(it, "resource_id", "")
        text = (it.text or "").strip()
        if text:
            lines.append(f"[{cid}] {text[:300]}")
    return "\n".join(lines), pkg


def generate_quiz(services: AlaServices, *, concept: str, n: int = 5,
                  difficulty: str = "medium") -> dict:
    label = concept.replace("concept:", "").replace("-", " ").strip()
    ev_text, pkg = _evidence(services, label or concept)
    questions = _llm_questions(services, label, ev_text, n, difficulty)
    source = "llm"
    if not questions:
        questions = _fallback_questions(concept, label, pkg, difficulty)
        source = "extractive"
    return {"concept": concept, "label": label, "difficulty": difficulty,
            "source": source, "questions": questions[:n]}


def _llm_questions(services: AlaServices, label: str, ev_text: str, n: int,
                   difficulty: str) -> list[dict]:
    from ala.llm.factory import available_provider
    provider = available_provider(services.settings)
    if provider is None or not ev_text.strip():
        return []
    # "/no_think" disables Qwen3's slow reasoning phase — quiz JSON needs no chain-of-thought,
    # and it cuts generation from ~2.5 min to well under a minute.
    prompt = (
        f"/no_think\n"
        f"You are an exam question writer. Using ONLY the evidence below, write {n} varied "
        f"quiz questions about \"{label}\" at {difficulty} difficulty. Vary the types across: "
        f"multiple_choice (exactly 4 options), true_false, short_answer.\n"
        f"Return ONLY a JSON array, no prose, no reasoning. Each element is an object:\n"
        f'{{"type":"multiple_choice"|"true_false"|"short_answer","question":str,'
        f'"options":[str] (4 options for multiple_choice, ["True","False"] for true_false, [] for short_answer),'
        f'"answer":str (must EXACTLY match one option for multiple_choice/true_false; a concise model answer for short_answer),'
        f'"explanation":str}}\n\nEVIDENCE:\n{ev_text}\n'
    )
    try:
        raw = provider.complete(prompt)
    except Exception as exc:                                  # noqa: BLE001
        log.warning("quiz LLM generation failed: %s", exc)
        return []
    return _parse(raw, difficulty)


def _parse(raw: str, difficulty: str) -> list[dict]:
    m = _JSON_ARRAY.search(raw or "")
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[dict] = []
    for q in data:
        if not isinstance(q, dict):
            continue
        qtype = str(q.get("type", "short_answer")).strip()
        if qtype not in _VALID_TYPES:
            qtype = "short_answer"
        question = str(q.get("question", "")).strip()
        answer = str(q.get("answer", "")).strip()
        if not question or not answer:
            continue
        opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        if qtype == "true_false":
            opts = ["True", "False"]
        if qtype == "multiple_choice" and len(opts) < 2:
            continue                                          # malformed MCQ → skip
        # ensure the answer is present among options for choice questions
        if qtype in ("multiple_choice", "true_false") and answer not in opts:
            opts = opts or []
            opts.append(answer)
        out.append({"type": qtype, "question": question, "options": opts,
                    "answer": answer, "explanation": str(q.get("explanation", "")).strip(),
                    "difficulty": difficulty})
    return out


def _fallback_questions(concept: str, label: str, pkg, difficulty: str) -> list[dict]:
    """No LLM → a grounded extractive short-answer question from the evidence."""
    from ala.agents import quizgen
    q = quizgen.generate_quiz(concept, list(pkg.items), difficulty=difficulty)
    return [{
        "type": "short_answer",
        "question": q["question"],
        "options": [],
        "answer": q.get("answer_key", ""),
        "explanation": ("Key ideas: " + ", ".join(q.get("key_terms", [])[:6])) if q.get("key_terms") else "",
        "difficulty": difficulty,
    }]
