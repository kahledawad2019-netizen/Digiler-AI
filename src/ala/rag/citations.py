"""GraphCitationManager — stable citation ids, an index, and grounding checks.

Assigns ``[C#]`` to chunk evidence and ``[K#]`` to concept (knowledge-graph)
evidence, keeps the resolvable index (resource, page/slide/timestamp, confidence)
for the Citation Explorer (Stage 15), and validates that every citation an answer
emits maps to a real source — the mechanism that keeps answers grounded.
"""

from __future__ import annotations

import re

from ala.rag.models import CitationRecord
from ala.retrieval.evidence.models import EvidenceItem, GraphEvidenceItem

_CITE = re.compile(r"\[(C\d+|K\d+)\]")
_SENT = re.compile(r"(?<=[.!?])\s+")


class GraphCitationManager:
    def chunk_citation(self, item: EvidenceItem, n: int) -> CitationRecord:
        return CitationRecord(
            cid=f"C{n}", kind="chunk", label=item.citation or item.resource_id,
            resource_id=item.resource_id, source_type=item.source_type,
            page=item.page, slide=item.slide, timestamp=item.timestamp,
            confidence=item.confidence)

    def concept_citation(self, ev: GraphEvidenceItem, n: int) -> CitationRecord:
        return CitationRecord(
            cid=f"K{n}", kind="concept", label=ev.concept,
            resource_id=(ev.source_resources[0] if ev.source_resources else ""),
            source_type="concept", confidence=ev.confidence)

    # -- grounding -------------------------------------------------------- #
    def check_grounding(self, answer: str, valid_ids: set[str]) -> dict:
        """A sentence is grounded iff it carries ≥1 *valid* citation."""
        cited = set(_CITE.findall(answer))
        invalid = sorted(cited - valid_ids)
        sentences = [s for s in _SENT.split(answer.strip()) if s.strip()]
        grounded = 0
        ungrounded: list[str] = []
        for s in sentences:
            ids = set(_CITE.findall(s))
            if ids and ids <= valid_ids:
                grounded += 1
            else:
                ungrounded.append(s)
        total = max(1, len(sentences))
        return {
            "grounding_ratio": round(grounded / total, 4),
            "grounded_sentences": grounded, "total_sentences": len(sentences),
            "citations_used": sorted(cited), "invalid_citations": invalid,
            "citation_valid": not invalid,
            "ungrounded_sentences": ungrounded,
        }

    def used_citations(self, answer: str, index: dict[str, CitationRecord]) -> list[CitationRecord]:
        seen: list[str] = []
        for cid in _CITE.findall(answer):
            if cid not in seen and cid in index:
                seen.append(cid)
        return [index[c] for c in seen]
