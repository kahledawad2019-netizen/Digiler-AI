"""CitationExplorer — build a unified, navigable citation index.

Takes any ``EvidencePackage`` (KB, GraphRAG or Research merged) and produces a
``CitationIndex`` of resolved ``CitationNode``s: chunk citations (``C#``), concept
/ graph citations (``K#``) and web citations (``W#``), each with a clickable link,
locator, confidence and provenance. This is the browser/source-explorer backend.
"""

from __future__ import annotations

from ala.explorer.models import CitationIndex, CitationNode, ExplorerConfig
from ala.explorer.resolver import CitationResolver
from ala.retrieval.evidence.models import EvidenceItem, EvidencePackage, GraphEvidenceItem


class CitationExplorer:
    def __init__(self, resolver: CitationResolver, config: ExplorerConfig | None = None) -> None:
        self.resolver = resolver
        self.config = config or ExplorerConfig()

    def build(self, pkg: EvidencePackage) -> CitationIndex:
        nodes: list[CitationNode] = []
        c = w = 0
        for it in pkg.items:
            if it.confidence < self.config.min_confidence:
                continue
            if it.source_type == "web":
                w += 1
                nodes.append(self.resolver.resolve(self._web_node(it, f"W{w}")))
            else:
                c += 1
                nodes.append(self.resolver.resolve(self._chunk_node(it, f"C{c}")))
            if len(nodes) >= self.config.max_citations:
                break
        for k, ev in enumerate(pkg.graph_evidence, start=1):
            nodes.append(self.resolver.resolve(self._concept_node(ev, f"K{k}")))
        return CitationIndex(query=pkg.query, nodes=nodes)

    # ------------------------------------------------------------------ #
    @staticmethod
    def _locator(it: EvidenceItem) -> str:
        if it.slide is not None:
            return f"slide {it.slide}"
        if it.timestamp is not None:
            m, s = divmod(int(it.timestamp), 60)
            return f"{m}:{s:02d}"
        if it.page is not None:
            pe = it.page_end
            return f"p.{it.page}" + (f"-{pe}" if pe and pe != it.page else "")
        return ""

    def _chunk_node(self, it: EvidenceItem, cid: str) -> CitationNode:
        return CitationNode(
            cid=cid, kind="chunk", label=it.citation or it.resource_id,
            source_type=it.source_type, resource_id=it.resource_id,
            title=it.document_title or it.resource_id, locator=self._locator(it),
            page=it.page, slide=it.slide, timestamp=it.timestamp, chunk_id=it.chunk_id,
            confidence=it.confidence, text=(it.text or "")[:280])

    def _web_node(self, it: EvidenceItem, cid: str) -> CitationNode:
        url = (it.metadata or {}).get("url", "")
        return CitationNode(
            cid=cid, kind="web", label=it.citation or url, source_type="web",
            resource_id=it.resource_id, title=it.document_title or it.resource_id,
            locator=(it.metadata or {}).get("domain", ""), link=url,
            confidence=it.confidence, text=(it.text or "")[:280])

    def _concept_node(self, ev: GraphEvidenceItem, cid: str) -> CitationNode:
        return CitationNode(
            cid=cid, kind="concept", label=ev.concept, source_type="concept",
            concept_id=ev.concept_id, graph_path=ev.path, title=ev.concept,
            locator=f"{ev.hop}-hop via {ev.relationship}" if ev.hop else "seed",
            confidence=ev.confidence,
            text=" -> ".join(ev.path) + (f"  (sources: {', '.join(ev.source_resources[:3])})"
                                         if ev.source_resources else ""))
