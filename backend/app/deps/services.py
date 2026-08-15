"""AlaServices — the single shared bridge to the existing ala platform.

Builds **one** service bundle (Qdrant local mode locks its path, so exactly one
GraphRAG/retrieval stack may exist per process) and lets every router reuse it:
GraphRAG, Student Model, concept graph, RL, Study Planner, Research Mode and the
Incremental Ingestor all come from one ``AgentService`` bundle; the Function
registry, Dashboard and Citation Explorer are constructed over the SAME handles.
No business logic is re-implemented — this only wires the reuse.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_instance: "AlaServices | None" = None


class AlaServices:
    def __init__(self) -> None:
        from ala.agents.service import AgentService
        from ala.catalog.repository import KnowledgeCatalog
        from ala.config.settings import load_settings
        from ala.dashboard.service import DashboardService
        from ala.functions.registry import FunctionRegistry
        from ala.functions.tools import build_functions

        self.settings = load_settings(None)                 # reads config/platform.yaml (ALA_CONFIG)
        self.agent_service = AgentService(self.settings)    # the ONE shared bundle (single Qdrant)
        self.bundle = self.agent_service.services           # graphrag/student_model/graph/rl/planner/research/ingestor
        self.catalog = KnowledgeCatalog.from_settings(self.settings)

        # function-calling registry over the SAME shared services (no second GraphRAG)
        t = getattr(self.settings, "tools", {}) or {}
        self.functions = FunctionRegistry()
        for spec in build_functions(self.bundle, python_timeout=float(t.get("python_timeout", 2.0)),
                                    allow_knowledge_update=bool(t.get("allow_knowledge_update", True))):
            self.functions.register(spec)

        # dashboard over the shared student model + graph + catalog
        self.dashboard = DashboardService(self.settings, student_model=self.bundle.student_model,
                                          graph=self.bundle.graph, catalog=self.catalog)

    # -- convenience handles -------------------------------------------- #
    @property
    def graphrag(self):
        return self.bundle.graphrag

    @property
    def student_model(self):
        return self.bundle.student_model

    @property
    def graph(self):
        return self.bundle.graph

    @property
    def rl(self):
        return self.bundle.rl

    @property
    def planner(self):
        return self.bundle.planner

    @property
    def research(self):
        return self.bundle.research

    def citation_index(self, package):
        from ala.explorer.explorer import CitationExplorer
        from ala.explorer.resolver import CitationResolver
        return CitationExplorer(CitationResolver(self.settings, self.catalog)).build(package)

    def close(self) -> None:
        self.agent_service.close()
        self.catalog.close()


def get_services() -> AlaServices:
    """Lazy process-wide singleton (built on first request; heavy: loads Qdrant + e5)."""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = AlaServices()
    return _instance


async def services_dependency() -> AlaServices:
    """Async FastAPI dependency — build/fetch the singleton off the event loop."""
    from starlette.concurrency import run_in_threadpool
    return await run_in_threadpool(get_services)


def shutdown_services() -> None:
    global _instance
    if _instance is not None:
        _instance.close()
        _instance = None
