"""GraphEvidenceMerger — unify graph-retrieval output into one Evidence Package.

Runs the graph retriever once and folds its two outputs — graph-aware **chunk**
evidence and concept-path **graph** evidence — into a single ``EvidencePackage``
via the existing ``EvidenceBuilder`` (no retrieval or item logic duplicated).
"""

from __future__ import annotations

from ala.rag.models import GraphRAGConfig
from ala.retrieval.evidence.builder import EvidenceBuilder
from ala.retrieval.evidence.models import EvidencePackage
from ala.retrieval.graphsearch.models import GraphRetrievalResult
from ala.retrieval.graphsearch.retriever import GraphRetriever


class GraphEvidenceMerger:
    def __init__(self, graph_retriever: GraphRetriever, evidence_builder: EvidenceBuilder,
                 config: GraphRAGConfig | None = None) -> None:
        self.graph_retriever = graph_retriever
        self.evidence_builder = evidence_builder
        self.config = config or GraphRAGConfig()

    def merge(self, question: str, *, top_k: int | None = None,
              filters: dict | None = None) -> tuple[EvidencePackage, GraphRetrievalResult]:
        k = top_k or self.config.top_k_chunks
        res = self.graph_retriever.retrieve_with_graph(question, top_k=k, filters=filters)
        pkg = self.evidence_builder.build_from_results(
            question, res.chunks, top_k=k, graph_evidence=res.graph_evidence,
            retriever_name="graphrag")
        return pkg, res
