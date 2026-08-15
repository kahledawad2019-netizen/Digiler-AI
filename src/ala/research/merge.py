"""ResearchEvidenceMerger — unify KB evidence with web evidence.

Turns downloaded web documents into ``EvidenceItem``s (source_type=web, domain +
URL provenance, typed citation) and merges them with the Knowledge-Base evidence
into one ranked ``EvidencePackage`` — the same object GraphRAG already consumes.
Source attribution and citations are never lost; graph evidence from the KB side
is carried through unchanged.
"""

from __future__ import annotations

import re

from ala.research.models import ResearchConfig, ScoredSource, WebDocument
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, SourceType
from ala.retrieval.search.normalize import normalize_query

_WORD = re.compile(r"[a-zA-Z][a-zA-Z\-]+")


def _terms(text: str) -> set[str]:
    return {w for w in (t.lower() for t in _WORD.findall(text)) if len(w) > 2}


def _passages(text: str, qterms: set[str], n: int = 2) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n{2,}", text) if len(p.split()) >= 15]
    if not paras:
        paras = [text.strip()[:600]] if text.strip() else []
    paras.sort(key=lambda p: len(_terms(p) & qterms), reverse=True)
    return paras[:n]


class ResearchEvidenceMerger:
    def __init__(self, config: ResearchConfig | None = None) -> None:
        self.config = config or ResearchConfig()

    def merge(self, kb_pkg: EvidencePackage,
              web_docs: list[tuple[ScoredSource, WebDocument]],
              query: str) -> EvidencePackage:
        qterms = _terms(query)
        web_items: list[EvidenceItem] = []
        for src, doc in web_docs:
            trust = src.score.trust
            for j, passage in enumerate(_passages(doc.text, qterms)):
                overlap = len(_terms(passage) & qterms) / (len(qterms) or 1)
                conf = round(min(1.0, 0.5 * trust + 0.5 * min(1.0, overlap)), 4)
                web_items.append(EvidenceItem(
                    rank=0, chunk_id=f"web:{doc.domain}:{j}", text=passage,
                    retrieval_score=conf, fused_score=conf, confidence=conf,
                    retrieval_reason=f"web source (trust {trust:.2f}, overlap {overlap:.2f})",
                    source_type=SourceType.WEB.value, resource_id=doc.domain or doc.url,
                    document_title=doc.title, citation=f"[{doc.title} — {doc.domain}]",
                    metadata={"url": doc.url, "domain": doc.domain, "published": doc.published,
                              "provider": src.result.provider, "trust": trust}))

        combined = list(kb_pkg.items) + web_items
        combined.sort(key=lambda it: it.confidence, reverse=True)
        for i, it in enumerate(combined):
            it.rank = i

        from statistics import mean
        confs = [it.confidence for it in combined]
        overall = round(mean(sorted(confs, reverse=True)[:3]), 4) if confs else 0.0
        stats = dict(kb_pkg.stats)
        stats.update({"n_web_items": len(web_items), "n_kb_items": len(kb_pkg.items),
                      "n_web_sources": len(web_docs)})
        return EvidencePackage(
            query=query, normalized_query=normalize_query(query), retriever="research",
            items=combined, graph_evidence=kb_pkg.graph_evidence,
            overall_confidence=overall, stats=stats)
