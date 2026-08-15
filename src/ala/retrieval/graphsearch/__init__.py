"""Stage 11 — Graph Retrieval Engine.

Additive layer that consumes the **Concept Graph** (Stage 10), the **Hybrid
Retriever** (Stage 7), and the **Evidence Package** (Stage 9) to produce
graph-aware chunk evidence *plus* graph (concept-path) evidence — without
touching any of those modules. Pipeline:

    query → hybrid seeds → query/seed → concept linking → multi-hop weighted
    concept expansion → per-resource graph score → graph-aware re-rank of the
    hybrid candidates → chunk evidence + graph evidence (citations preserved).
"""

from ala.retrieval.graphsearch.config import GraphRetrievalConfig
from ala.retrieval.graphsearch.expander import GraphExpander
from ala.retrieval.graphsearch.linker import QueryConceptLinker
from ala.retrieval.graphsearch.models import ExpandedConcept, GraphRetrievalResult
from ala.retrieval.graphsearch.retriever import GraphRetriever

__all__ = [
    "GraphRetrievalConfig", "GraphExpander", "QueryConceptLinker",
    "ExpandedConcept", "GraphRetrievalResult", "GraphRetriever",
]
