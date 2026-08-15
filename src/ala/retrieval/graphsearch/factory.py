"""Factory — wire a ready GraphRetriever from settings (graph + hybrid stack)."""

from __future__ import annotations

from dataclasses import dataclass

from ala.config.settings import Settings
from ala.graph.store import GraphStore
from ala.retrieval.graphsearch.config import GraphRetrievalConfig
from ala.retrieval.graphsearch.retriever import GraphRetriever
from ala.retrieval.search.factory import Retrievers, build_retrievers


@dataclass
class GraphRetrievers:
    graph: GraphRetriever
    base: Retrievers                 # dense / bm25 / hybrid + close()

    def close(self) -> None:
        self.base.close()


def build_graph_retriever(settings: Settings,
                          config: GraphRetrievalConfig | None = None) -> GraphRetrievers:
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    store = GraphStore(settings.abspath(loc))
    if not store.exists():
        raise FileNotFoundError(
            f"Concept graph not found at {store.db_path}. Build it first: `ala graph build`."
        )
    graph = store.load()
    base = build_retrievers(settings)
    cfg = config or GraphRetrievalConfig.from_settings(settings)
    return GraphRetrievers(graph=GraphRetriever(graph, base.hybrid, cfg), base=base)
