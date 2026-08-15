"""Function-calling value types (OpenAI-style tool schemas)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class FunctionSpec:
    """A callable tool with a JSON-schema description (for LLM function calling)."""
    name: str
    description: str
    func: Callable[..., dict]
    parameters: dict = field(default_factory=dict)     # {arg: {"type","description","required"}}
    safe: bool = True                                  # sandboxed / side-effect-free
    mutating: bool = False                             # grows/changes the KB

    def schema(self) -> dict:
        props, required = {}, []
        for arg, spec in self.parameters.items():
            props[arg] = {"type": spec.get("type", "string"),
                          "description": spec.get("description", "")}
            if spec.get("required"):
                required.append(arg)
        return {"name": self.name, "description": self.description,
                "parameters": {"type": "object", "properties": props, "required": required}}


@dataclass
class FunctionCall:
    name: str
    arguments: dict = field(default_factory=dict)


@dataclass
class FunctionResult:
    name: str
    ok: bool
    result: dict | None = None
    error: str | None = None
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "result": self.result,
                "error": self.error, "latency_ms": self.latency_ms}
