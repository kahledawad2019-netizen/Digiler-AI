"""EvidenceBuilder — turn ranked RetrievalResults into a rich EvidencePackage.

Resolves chunk text, derives the source type + typed citation, computes a
calibrated confidence, and writes an explicit retrieval_reason so every item is
explainable. Depends only on the Retriever interface + a text resolver (+ an
optional catalog for document titles) — no retrieval logic is duplicated.
"""

from __future__ import annotations

from statistics import mean

from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, SourceType
from ala.retrieval.search.normalize import normalize_query
from ala.retrieval.types import RetrievalResult


class EvidenceBuilder:
    def __init__(self, retriever, text_resolver=None, catalog=None,
                 retriever_name: str = "hybrid") -> None:
        self.retriever = retriever
        self.text_resolver = text_resolver
        self.catalog = catalog
        self.retriever_name = retriever_name
        self._title_cache: dict[str, str | None] = {}

    def build(self, query: str, *, top_k: int = 8, filters: dict | None = None) -> EvidencePackage:
        results = self.retriever.retrieve(query, top_k=top_k, filters=filters)
        return self.build_from_results(query, results, top_k=top_k)

    def build_from_results(self, query: str, results: list[RetrievalResult], *,
                           top_k: int = 8, graph_evidence: list | None = None,
                           retriever_name: str | None = None) -> EvidencePackage:
        """Build a package from already-retrieved results (no re-retrieval).

        Lets the GraphRAG layer (Stage 12) attach ``graph_evidence`` from the
        graph retriever without duplicating any item-building logic.
        """
        if self.text_resolver is not None:
            self.text_resolver.attach(results)

        k = top_k or len(results)
        max_fused = max((r.score for r in results), default=0.0) or 1.0
        items = [self._item(r, i, k, max_fused) for i, r in enumerate(results)]

        confidences = [it.confidence for it in items]
        overall = round(mean(sorted(confidences, reverse=True)[:3]), 4) if confidences else 0.0
        return EvidencePackage(
            query=query, normalized_query=normalize_query(query),
            retriever=retriever_name or self.retriever_name, items=items,
            graph_evidence=list(graph_evidence or []),
            overall_confidence=overall, stats=self._stats(items),
        )

    # ------------------------------------------------------------------ #
    def _item(self, r: RetrievalResult, rank: int, top_k: int, max_fused: float) -> EvidenceItem:
        p = r.payload
        cs = r.component_scores
        dense = cs.get("dense")
        bm25 = cs.get("bm25")
        semantic = dense if dense is not None else None
        source_type = _source_type(p)
        confidence = _confidence(r.score, max_fused, semantic, rank, top_k)
        return EvidenceItem(
            rank=rank, chunk_id=r.chunk_id, parent_chunk=p.get("parent_id"),
            text=r.text or "",
            retrieval_score=round(r.score, 6), dense_score=dense, bm25_score=bm25,
            fused_score=round(cs.get("rrf", r.score), 6), semantic_similarity=semantic,
            confidence=confidence, retrieval_reason=_reason(cs, r.score),
            source_type=source_type, resource_id=p.get("resource_id", ""),
            document_title=self._title(p.get("resource_id", "")),
            heading=p.get("heading"), section_path=p.get("section_path") or [],
            page=p.get("page"), page_end=p.get("page_end"), slide=p.get("slide"),
            timestamp=p.get("timestamp"), language=p.get("language"),
            citation=_citation(source_type, p, self._title(p.get("resource_id", ""))),
            metadata={k: p[k] for k in ("track", "course", "module", "chunk_type",
                                        "topics", "keywords") if k in p},
        )

    def _title(self, resource_id: str) -> str | None:
        if not resource_id:
            return None
        if resource_id not in self._title_cache:
            title = None
            if self.catalog is not None:
                meta = self.catalog.get(resource_id)
                title = meta.title if meta else None
            self._title_cache[resource_id] = title or resource_id.split(".")[-1].replace("-", " ").title()
        return self._title_cache[resource_id]

    @staticmethod
    def _stats(items: list[EvidenceItem]) -> dict:
        from collections import Counter
        by_type = Counter(it.source_type for it in items)
        return {
            "n_items": len(items),
            "n_resources": len({it.resource_id for it in items}),
            "by_source_type": dict(by_type),
        }


# --------------------------------------------------------------------------- #
def _source_type(payload: dict) -> str:
    if payload.get("slide") is not None:
        return SourceType.SLIDE.value
    if payload.get("timestamp") is not None:
        return SourceType.VIDEO.value
    if payload.get("url") or payload.get("domain"):
        return SourceType.WEB.value
    if payload.get("page") is not None:
        return SourceType.PDF.value
    if payload.get("chunk_type") == "notebook_cell":
        return SourceType.NOTEBOOK.value
    return SourceType.DOCUMENT.value


def _confidence(fused: float, max_fused: float, semantic: float | None,
                rank: int, top_k: int) -> float:
    rank_factor = 1.0 - rank / max(top_k, 1)
    if semantic is not None:
        return round(min(1.0, max(0.0, 0.5 * semantic + 0.5 * rank_factor)), 4)
    norm = fused / max_fused if max_fused else 0.0
    return round(min(1.0, max(0.0, 0.5 * norm + 0.5 * rank_factor)), 4)


def _reason(cs: dict, fused: float) -> str:
    parts = []
    if "dense_rank" in cs:
        parts.append(f"dense #{int(cs['dense_rank'])} (cos {cs.get('dense', 0):.3f})")
    if "bm25_rank" in cs:
        parts.append(f"BM25 #{int(cs['bm25_rank'])} (score {cs.get('bm25', 0):.2f})")
    prefix = " + ".join(parts) if parts else "retrieved"
    return f"{prefix} -> fused {fused:.4f}"


def _citation(source_type: str, payload: dict, title: str | None) -> str:
    src = title or payload.get("resource_id", "")
    if source_type == SourceType.SLIDE.value:
        loc = f"slide {payload['slide']}"
    elif source_type == SourceType.VIDEO.value:
        m, s = divmod(int(payload["timestamp"]), 60)
        loc = f"{m}:{s:02d}"
    elif source_type == SourceType.PDF.value:
        pe = payload.get("page_end")
        loc = f"p.{payload['page']}" + (f"-{pe}" if pe and pe != payload["page"] else "")
    elif source_type == SourceType.WEB.value:
        loc = payload.get("domain", "web")
    else:
        loc = ""
    head = payload.get("heading") or (payload.get("section_path") or [""])[-1]
    return f"[{src}" + (f", {loc}" if loc else "") + (f", {head}" if head else "") + "]"
