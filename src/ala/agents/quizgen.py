"""Extractive quiz generation + grading (no LLM required).

Builds a question + answer-key from retrieved evidence (the Quiz Agent), and grades
a learner's answer by key-term recall against that evidence (the Evaluator Agent).
Grounded by construction — the answer key is real corpus text with its citation.
"""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-zA-Z][a-zA-Z\-]+")
_SENT = re.compile(r"(?<=[.!?])\s+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "with", "and", "or", "is", "are",
         "be", "this", "that", "it", "its", "as", "by", "from", "at", "we", "you", "can",
         "will", "which", "when", "how", "what", "was", "were", "has", "have", "using", "used",
         "also", "such", "these", "those", "them", "they", "our", "your", "into", "than", "then"}


def _terms(text: str) -> set[str]:
    return {w for w in (t.lower() for t in _WORD.findall(text)) if len(w) > 2 and w not in _STOP}


def key_terms(sentence: str, concept: str, k: int = 8) -> list[str]:
    terms = list(_terms(sentence) | _terms(concept))
    terms.sort(key=lambda t: (t not in _terms(concept), -len(t)))     # concept terms first
    return terms[:k]


def _best_sentence(text: str, concept: str) -> str:
    ct = _terms(concept)
    sents = [s.strip() for s in _SENT.split(text.strip()) if len(s.split()) >= 6]
    if not sents:
        return text.strip()[:240]
    return max(sents, key=lambda s: len(_terms(s) & ct))[:280]


def generate_quiz(concept: str, evidence_items: list, difficulty: str = "medium") -> dict:
    top = next((it for it in evidence_items if (it.text or "").strip()), None)
    if top is None:
        return {"question": f"Explain the concept of '{concept}'.", "answer_key": "",
                "key_terms": key_terms(concept, concept), "source": "", "difficulty": difficulty}
    sentence = _best_sentence(top.text, concept)
    kinds = {"very-easy": "Define", "easy": "Define", "medium": "Explain",
             "hard": "Explain in detail and give an example of", "very-hard": "Critically analyse"}
    stem = kinds.get(difficulty, "Explain")
    return {
        "question": f"{stem} the concept of '{concept}'.",
        "answer_key": sentence,
        "key_terms": key_terms(sentence, concept),
        "source": getattr(top, "citation", "") or getattr(top, "resource_id", ""),
        "difficulty": difficulty,
    }


def grade(student_answer: str, key_terms_list: list[str], *, threshold: float = 0.4) -> dict:
    keys = set(key_terms_list)
    if not keys:
        return {"correct": False, "score": 0.0, "covered": [], "missing": [],
                "feedback": "No answer key available."}
    st = _terms(student_answer)
    covered = sorted(keys & st)
    missing = sorted(keys - st)
    score = round(len(covered) / len(keys), 3)
    correct = score >= threshold
    if correct:
        feedback = f"Correct — you covered the key ideas ({', '.join(covered[:4])})."
    else:
        feedback = f"Not quite. Review these: {', '.join(missing[:4]) or 'the key ideas'}."
    return {"correct": correct, "score": score, "covered": covered, "missing": missing,
            "feedback": feedback}
