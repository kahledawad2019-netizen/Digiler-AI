"""EvidenceFormatter — render an EvidencePackage for the LLM (and Citation Explorer).

``to_context`` produces the exact grounded-prompt text the generator receives —
numbered, cited evidence blocks with an instruction to cite ``[n]``. The LLM
never sees raw retrieval rows, only this. ``citation_index`` emits typed
navigation data (page / slide / timestamp) that the future Citation Explorer uses.
"""

from __future__ import annotations

from ala.retrieval.evidence.models import EvidencePackage

_INSTRUCTION = (
    "Answer the question using ONLY the evidence below. Cite every claim with the "
    "bracketed source number, e.g. [1]. If the evidence is insufficient, say so."
)


class EvidenceFormatter:
    def to_context(self, package: EvidencePackage, *, max_chars_per_item: int = 800,
                   include_scores: bool = False) -> str:
        lines = [_INSTRUCTION, "", f"QUESTION: {package.query}", "", "EVIDENCE:"]
        for i, it in enumerate(package.items, 1):
            text = it.text.strip().replace("\n", " ")
            if len(text) > max_chars_per_item:
                text = text[:max_chars_per_item].rstrip() + " …"
            lines.append(f"[{i}] {it.citation}")
            if include_scores:
                lines.append(f"    (confidence {it.confidence}; {it.retrieval_reason})")
            lines.append(f"    {text}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def citation_index(self, package: EvidencePackage) -> list[dict]:
        """Typed citation records for the Citation Explorer (page/slide/timestamp)."""
        return [
            {
                "n": i, "citation": it.citation, "source_type": it.source_type,
                "resource_id": it.resource_id, "document_title": it.document_title,
                "chunk_id": it.chunk_id, "page": it.page, "page_end": it.page_end,
                "slide": it.slide, "timestamp": it.timestamp, "heading": it.heading,
            }
            for i, it in enumerate(package.items, 1)
        ]
