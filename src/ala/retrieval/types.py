"""Shared retrieval types (neutral location to avoid import cycles).

``RetrievalResult`` is the uniform unit every retriever returns (never a raw DB
row), carrying the scores of each component so fusion and the Evidence Package
(Stage 9) are fully explainable. Lives here — not under ``search`` — so both the
``bm25`` and ``search`` packages can import it without a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class RetrievalResult:
    chunk_id: str
    score: float
    rank: int
    source: str                                   # "dense" | "bm25" | "hybrid"
    payload: dict[str, Any] = field(default_factory=dict)
    component_scores: dict[str, float] = field(default_factory=dict)
    text: str | None = None                       # populated for rerank / evidence

    def citation(self) -> str:
        p = self.payload
        loc = ""
        if p.get("slide") is not None:
            loc = f"slide {p['slide']}"
        elif p.get("timestamp") is not None:
            m, s = divmod(int(p["timestamp"]), 60)
            loc = f"{m}:{s:02d}"
        elif p.get("page") is not None:
            loc = f"p.{p['page']}"
        head = p.get("heading") or (p.get("section_path") or [""])[-1]
        return f"[{p.get('resource_id', self.chunk_id)}" + (f", {loc}" if loc else "") + \
               (f", {head}" if head else "") + "]"


@runtime_checkable
class Retriever(Protocol):
    def retrieve(self, query: str, *, top_k: int = 10,
                 filters: dict[str, Any] | None = None) -> list[RetrievalResult]:
        ...
