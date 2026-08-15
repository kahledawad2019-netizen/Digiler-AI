"""Research-Mode value types + configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from ala.core.enums import _StrEnum


class ConfidenceLevel(_StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ConfidenceReport:
    score: float
    level: str
    needs_research: bool
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"score": self.score, "level": self.level,
                "needs_research": self.needs_research, "signals": self.signals}


@dataclass
class WebResult:
    """A raw search hit (before download/parse)."""
    title: str
    url: str
    snippet: str = ""
    published: str | None = None            # ISO date if the provider gives one
    provider: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def domain(self) -> str:
        from urllib.parse import urlparse
        return (urlparse(self.url).netloc or "").lower().removeprefix("www.")


@dataclass
class SourceScore:
    authority: float
    freshness: float
    educational: float
    domain_quality: float
    citation_quality: float
    spam: float                              # 0 = clean, 1 = spammy
    duplicate: bool
    trust: float                             # overall [0,1]

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ScoredSource:
    result: WebResult
    score: SourceScore


@dataclass
class WebDocument:
    """A downloaded, cleaned source ready to become a LearningResource."""
    url: str
    title: str
    text: str
    doc_type: str = "web"
    domain: str = ""
    published: str | None = None
    path: str | None = None                  # local file once saved for ingestion


@dataclass
class ResearchResult:
    question: str
    answer: str
    confidence: ConfidenceReport
    used_web: bool
    sources: list[dict] = field(default_factory=list)     # ranked source records
    citations: list[dict] = field(default_factory=list)
    ingested: list[str] = field(default_factory=list)     # resource_ids grown into the KB
    session_id: str = ""
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "question": self.question, "answer": self.answer,
            "confidence": self.confidence.to_dict(), "used_web": self.used_web,
            "sources": self.sources, "citations": self.citations,
            "ingested": self.ingested, "session_id": self.session_id, "stats": self.stats,
        }


@dataclass
class ResearchConfig:
    provider: str = "disabled"               # disabled | duckduckgo | tavily | google
    api_key: str = ""
    google_cx: str = ""
    max_results: int = 6
    top_sources: int = 3
    confidence_threshold: float = 0.70       # score below → trigger web research
    high_threshold: float = 0.72
    low_threshold: float = 0.55
    min_source_trust: float = 0.4
    auto_approve: bool = False
    raw_subdir: str = "research"             # under knowledge_base/raw/<track>/…
    research_track: str = "research"
    research_course: str = "web"
    bm25_ref: float = 22.0                   # BM25 score treated as "confident"
    support_ref: int = 5                     # context chunks treated as "enough"
    # Only signals that actually discriminate in/out-of-corpus (calibrated on the
    # real corpus, Stage 14): semantic similarity, evidence agreement, BM25 strength.
    # citation/support/graph are ~constant under the extractive generator → excluded.
    weights: dict = field(default_factory=lambda: {
        "semantic": 0.55, "agreement": 0.30, "bm25": 0.15})

    @classmethod
    def from_settings(cls, settings) -> "ResearchConfig":
        import os
        r = (getattr(settings, "research", None) or {}) if settings else {}
        ws = r.get("web_search", {}) or {}
        conf = r.get("confidence", {}) or {}
        w = dict(cls().weights); w.update(conf.get("weights", {}) or {})
        # Environment variables override config (API keys should never live in YAML).
        return cls(
            provider=os.environ.get("ALA_RESEARCH_PROVIDER", str(ws.get("provider", "disabled"))),
            api_key=os.environ.get("ALA_RESEARCH_API_KEY", str(ws.get("api_key", ""))),
            google_cx=os.environ.get("ALA_RESEARCH_GOOGLE_CX", str(ws.get("google_cx", ""))),
            max_results=int(os.environ.get("ALA_RESEARCH_MAX_RESULTS", ws.get("max_results", 6))),
            top_sources=int(ws.get("top_sources", 3)),
            confidence_threshold=float(conf.get("threshold", 0.70)),
            high_threshold=float(conf.get("high_threshold", 0.72)),
            low_threshold=float(conf.get("low_threshold", 0.55)),
            min_source_trust=float(r.get("min_source_trust", 0.4)),
            auto_approve=bool(r.get("auto_approve", False)),
            raw_subdir=str(r.get("raw_subdir", "research")),
            research_track=str(r.get("research_track", "research")),
            research_course=str(r.get("research_course", "web")),
            bm25_ref=float(conf.get("bm25_ref", 22.0)),
            support_ref=int(conf.get("support_ref", 5)),
            weights=w,
        )
