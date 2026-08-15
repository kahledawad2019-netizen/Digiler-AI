"""FunctionService — wire the function-calling registry over the shared services."""

from __future__ import annotations

from ala.functions.models import FunctionResult
from ala.functions.registry import FunctionRegistry
from ala.functions.tools import build_functions


class FunctionService:
    def __init__(self, settings) -> None:
        from ala.agents.service import AgentServices
        self.settings = settings
        self.services = AgentServices(settings)          # shared handles (single source of truth)
        t = (getattr(settings, "tools", None) or {})
        self.registry = FunctionRegistry()
        for spec in build_functions(self.services,
                                    python_timeout=float(t.get("python_timeout", 2.0)),
                                    allow_knowledge_update=bool(t.get("allow_knowledge_update", True))):
            self.registry.register(spec)

    def schemas(self) -> list[dict]:
        return self.registry.schemas()

    def call(self, name: str, **arguments) -> FunctionResult:
        return self.registry.dispatch(name, arguments)

    def close(self) -> None:
        self.services.close()
