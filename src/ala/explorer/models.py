"""Citation Explorer value types."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class CitationNode:
    """One resolved, navigable citation."""
    cid: str                      # C1 (chunk) | K1 (concept) | W1 (web)
    kind: str                     # chunk | concept | web
    label: str
    source_type: str              # pdf | slide | video | notebook | web | document | concept
    resource_id: str = ""
    title: str = ""
    locator: str = ""             # "p.4" | "slide 3" | "1:23"
    page: int | None = None
    slide: int | None = None
    timestamp: float | None = None
    chunk_id: str = ""
    concept_id: str = ""
    graph_path: list[str] = field(default_factory=list)
    confidence: float = 0.0
    link: str = ""                # file URI (+fragment) | web url | concept:<id>
    resolvable: bool = False
    text: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class SourceRecord:
    """A source (resource / domain) grouping its citations."""
    resource_id: str
    title: str
    source_type: str
    n_citations: int
    link: str
    citations: list[str] = field(default_factory=list)     # cids

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class CitationIndex:
    query: str
    nodes: list[CitationNode] = field(default_factory=list)

    # -- filtering (evidence filtering) --------------------------------- #
    def filter(self, *, kind: str | None = None, source_type: str | None = None,
               resource_id: str | None = None, min_confidence: float = 0.0,
               resolvable: bool | None = None) -> "CitationIndex":
        out = [n for n in self.nodes
               if (kind is None or n.kind == kind)
               and (source_type is None or n.source_type == source_type)
               and (resource_id is None or n.resource_id == resource_id)
               and (resolvable is None or n.resolvable == resolvable)
               and n.confidence >= min_confidence]
        return CitationIndex(self.query, out)

    # -- source explorer ------------------------------------------------- #
    def sources(self) -> list[SourceRecord]:
        by: dict[str, SourceRecord] = {}
        for n in self.nodes:
            key = n.resource_id or n.cid
            rec = by.get(key)
            if rec is None:
                by[key] = SourceRecord(n.resource_id, n.title or n.label, n.source_type,
                                       1, n.link, [n.cid])
            else:
                rec.n_citations += 1
                rec.citations.append(n.cid)
        return sorted(by.values(), key=lambda r: r.n_citations, reverse=True)

    # -- stats ----------------------------------------------------------- #
    def stats(self) -> dict:
        chunks = [n for n in self.nodes if n.kind == "chunk"]
        web = [n for n in self.nodes if n.kind == "web"]
        located = [n for n in chunks if n.locator]
        return {
            "n_citations": len(self.nodes),
            "by_kind": dict(Counter(n.kind for n in self.nodes)),
            "by_source_type": dict(Counter(n.source_type for n in self.nodes)),
            "n_sources": len({n.resource_id for n in self.nodes if n.resource_id}),
            "resolvable_rate": round(sum(n.resolvable for n in self.nodes) / len(self.nodes), 4)
            if self.nodes else 0.0,
            "locator_coverage": round(len(located) / len(chunks), 4) if chunks else 0.0,
            "web_citations": len(web),
            "mean_confidence": round(sum(n.confidence for n in self.nodes) / len(self.nodes), 4)
            if self.nodes else 0.0,
        }

    def to_dict(self) -> dict:
        return {"query": self.query, "nodes": [n.to_dict() for n in self.nodes],
                "stats": self.stats(), "sources": [s.to_dict() for s in self.sources()]}


@dataclass
class ExplorerConfig:
    max_citations: int = 40
    min_confidence: float = 0.0

    @classmethod
    def from_settings(cls, settings) -> "ExplorerConfig":
        e = (getattr(settings, "explorer", None) or {}) if settings else {}
        return cls(max_citations=int(e.get("max_citations", 40)),
                   min_confidence=float(e.get("min_confidence", 0.0)))
