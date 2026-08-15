"""GraphRAG value types — the structured reasoning context + grounded answer.

All pydantic/dataclass so the context and answer serialize cleanly for the CLI,
the benchmark, and the future dashboard. The ``ReasoningContext`` is the single
object the prompt builder renders — the LLM sees nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CitationRecord:
    cid: str                       # "C1" (chunk) | "K1" (concept)
    kind: str                      # "chunk" | "concept"
    label: str                     # citation string / concept name
    resource_id: str = ""
    source_type: str = "document"
    page: int | None = None
    slide: int | None = None
    timestamp: float | None = None
    confidence: float = 0.0

    def locator(self) -> str:
        if self.slide is not None:
            return f"slide {self.slide}"
        if self.timestamp is not None:
            m, s = divmod(int(self.timestamp), 60)
            return f"{m}:{s:02d}"
        if self.page is not None:
            return f"p.{self.page}"
        return ""


@dataclass
class ContextChunk:
    cid: str                       # citation id "C1"
    text: str
    citation: str
    resource_id: str
    source_type: str
    confidence: float
    tokens: int


@dataclass
class ContextConcept:
    cid: str                       # citation id "K1"
    concept: str
    hop: int
    relationship: str
    path: list[str]
    confidence: float


@dataclass
class ContextRelation:
    source: str
    relationship: str
    target: str


@dataclass
class ReasoningContext:
    question: str
    chunks: list[ContextChunk] = field(default_factory=list)
    concepts: list[ContextConcept] = field(default_factory=list)
    relations: list[ContextRelation] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    neighbor_concepts: list[str] = field(default_factory=list)
    citations: dict[str, CitationRecord] = field(default_factory=dict)
    reasoning_trace: list[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    token_budget: int = 0
    tokens_used: int = 0

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "chunks": [c.__dict__ for c in self.chunks],
            "concepts": [c.__dict__ for c in self.concepts],
            "relations": [r.__dict__ for r in self.relations],
            "prerequisites": self.prerequisites,
            "neighbor_concepts": self.neighbor_concepts,
            "reasoning_trace": self.reasoning_trace,
            "overall_confidence": self.overall_confidence,
            "token_budget": self.token_budget,
            "tokens_used": self.tokens_used,
        }


@dataclass
class GraphRAGAnswer:
    question: str
    answer: str
    citations: list[CitationRecord] = field(default_factory=list)   # cited in the answer
    reasoning_trace: list[str] = field(default_factory=list)
    confidence: float = 0.0
    grounding: dict = field(default_factory=dict)                    # ratio, ungrounded, valid
    generator: str = "extractive-grounded"
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "question": self.question, "answer": self.answer,
            "citations": [c.__dict__ for c in self.citations],
            "reasoning_trace": self.reasoning_trace, "confidence": self.confidence,
            "grounding": self.grounding, "generator": self.generator, "stats": self.stats,
        }


@dataclass
class GraphRAGConfig:
    top_k_chunks: int = 8              # chunk evidence pulled from graph retrieval
    context_chunks: int = 5           # chunks kept in the reasoning context
    context_concepts: int = 8         # concepts kept in the reasoning context
    token_budget: int = 1800          # context token budget (chunks)
    max_chunk_tokens: int = 320       # truncate a single chunk to this
    dedupe_by: str = "resource_heading"
    min_confidence: float = 0.0       # drop evidence below this

    @classmethod
    def from_settings(cls, settings) -> "GraphRAGConfig":
        g = (getattr(settings, "graphrag", None) or {}) if settings else {}
        return cls(
            top_k_chunks=int(g.get("top_k_chunks", 8)),
            context_chunks=int(g.get("context_chunks", 5)),
            context_concepts=int(g.get("context_concepts", 8)),
            token_budget=int(g.get("token_budget", 1800)),
            max_chunk_tokens=int(g.get("max_chunk_tokens", 320)),
            dedupe_by=str(g.get("dedupe_by", "resource_heading")),
            min_confidence=float(g.get("min_confidence", 0.0)),
        )
