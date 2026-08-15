"""Generation backends behind a single interface (interface-over-concretes).

``ExtractiveGroundedGenerator`` is the **default** — dependency-free, offline,
and grounded *by construction*: it only ever emits real evidence sentences with
their citation tags, so it cannot hallucinate. This mirrors the embedding
layer's dependency-free default (HashingEmbedder) — a real strategy, not a mock.

``LLMBackedGenerator`` wraps any ``LLMClient`` (e.g. ``OpenAICompatibleLLM``,
a real HTTP adapter for a local/remote OpenAI-compatible server) and hands it
**only** the structured prompt. It is a clean extension point; it is never
exercised by the tests/benchmark (no network in CI).
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from ala.rag.models import ReasoningContext

_WORD = re.compile(r"[a-zA-Z][a-zA-Z\-]+")
_SENT = re.compile(r"(?<=[.!?])\s+")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "with", "and", "or",
         "is", "are", "what", "how", "why", "when", "which", "does", "do", "explain"}


@runtime_checkable
class AnswerGenerator(Protocol):
    name: str
    def answer(self, context: ReasoningContext, prompt: str) -> str: ...


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, prompt: str, **kw) -> str: ...


# --------------------------------------------------------------------------- #
def _terms(text: str) -> set[str]:
    return {w for w in (t.lower() for t in _WORD.findall(text)) if len(w) > 2 and w not in _STOP}


def _clean(sent: str) -> str:
    sent = " ".join(sent.replace("•", " ").replace("\n", " ").split()).strip(" -:;,")
    if len(sent) > 260:
        sent = sent[:260].rsplit(" ", 1)[0] + " …"
    return sent


def _best_sentence(text: str, qterms: set[str]) -> str:
    """Return a single clean sentence (no internal sentence breaks) best matching
    the question — so a leading citation stays attached under grounding checks."""
    sents = [s.strip() for s in _SENT.split(text.strip()) if len(s.split()) >= 4]
    if not sents:
        return _clean(text)
    best = max(sents, key=lambda s: len(_terms(s) & qterms))
    return _clean(best)


class ExtractiveGroundedGenerator:
    """Compose a cited answer strictly from context evidence (no hallucination)."""

    name = "extractive-grounded"

    def __init__(self, max_sentences: int = 3) -> None:
        self.max_sentences = max_sentences

    def answer(self, context: ReasoningContext, prompt: str = "") -> str:
        if not context.chunks:
            return "The available course materials do not contain enough information to answer this question."
        qterms = _terms(context.question)
        parts: list[str] = []
        if context.concepts:
            lead = ", ".join(f"{c.concept} [{c.cid}]" for c in context.concepts[:3])
            parts.append(f"Key concepts: {lead}.")
        # leading citation per sentence → robust to internal periods in the source
        seen: set[str] = set()
        for ch in context.chunks[:self.max_sentences]:
            sent = _best_sentence(ch.text, qterms).rstrip(".")
            if not sent or sent in seen:
                continue
            seen.add(sent)
            parts.append(f"[{ch.cid}] {sent}.")
        return " ".join(parts)


class LLMBackedGenerator:
    """Adapter: send the structured prompt to a real LLM (extension point).

    If the LLM call fails or returns nothing (server error, model unloaded, timeout),
    it degrades to the grounded extractive generator instead of raising — the answer
    is always non-empty and cited, never a 500."""

    def __init__(self, client: LLMClient, name: str = "llm",
                 fallback: "AnswerGenerator | None" = None) -> None:
        self.client = client
        self.name = name
        self._fallback = fallback or ExtractiveGroundedGenerator()

    def answer(self, context: ReasoningContext, prompt: str) -> str:
        try:
            out = self.client.complete(prompt)
            if out and out.strip():
                return out
        except Exception as exc:                              # noqa: BLE001
            import logging
            logging.getLogger("ala.rag.llm").warning(
                "LLM generation failed (%s); using grounded extractive fallback", exc)
        return self._fallback.answer(context, prompt)


class OpenAICompatibleLLM:
    """Real HTTP client for any OpenAI-compatible /chat/completions endpoint.

    Config via ``settings.graphrag.llm`` or env (ALA_LLM_BASE_URL / ALA_LLM_API_KEY
    / ALA_LLM_MODEL). Uses only stdlib ``urllib`` (no new dependency). Not called
    in tests/benchmark — this is the seam for a local Qwen2.5 / vLLM server.
    """

    def __init__(self, base_url: str, model: str, api_key: str = "",
                 temperature: float = 0.0, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings) -> "OpenAICompatibleLLM | None":
        import os
        g = (getattr(settings, "graphrag", None) or {}).get("llm", {}) if settings else {}
        base = os.environ.get("ALA_LLM_BASE_URL", g.get("base_url", ""))
        model = os.environ.get("ALA_LLM_MODEL", g.get("model", ""))
        if not base or not model:
            return None
        return cls(base, model, os.environ.get("ALA_LLM_API_KEY", g.get("api_key", "")),
                   float(g.get("temperature", 0.0)))

    def complete(self, prompt: str, **kw) -> str:
        import json
        import urllib.request
        body = json.dumps({
            "model": self.model, "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"].strip()
