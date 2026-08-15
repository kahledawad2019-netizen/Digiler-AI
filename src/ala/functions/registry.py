"""FunctionRegistry — validate + dispatch tool calls (the function-calling runtime).

An LLM (or the Coordinator) emits ``{name, arguments}``; the registry validates the
arguments against the tool's schema (required present, basic coercion, no unknown
args) and executes the tool through its underlying existing service, returning a
structured ``FunctionResult``. Errors are caught and reported, never raised at the
caller — a safe execution boundary.
"""

from __future__ import annotations

import time

from ala.functions.models import FunctionCall, FunctionResult, FunctionSpec

_COERCE = {"number": float, "integer": int, "boolean": lambda v: str(v).lower() in ("1", "true", "yes"),
           "string": str}


class FunctionRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, FunctionSpec] = {}

    def register(self, spec: FunctionSpec) -> None:
        self._specs[spec.name] = spec

    def names(self) -> list[str]:
        return list(self._specs)

    def get(self, name: str) -> FunctionSpec | None:
        return self._specs.get(name)

    def schemas(self) -> list[dict]:
        return [s.schema() for s in self._specs.values()]

    # ------------------------------------------------------------------ #
    def _validate(self, spec: FunctionSpec, args: dict) -> dict:
        declared = set(spec.parameters)
        unknown = set(args) - declared
        if unknown:
            raise ValueError(f"unknown argument(s): {', '.join(sorted(unknown))}")
        out = dict(args)
        for arg, meta in spec.parameters.items():
            if meta.get("required") and arg not in out:
                raise ValueError(f"missing required argument: {arg}")
            if arg in out and isinstance(out[arg], str):
                t = meta.get("type", "string")
                if t in _COERCE and t != "string":
                    try:
                        out[arg] = _COERCE[t](out[arg])
                    except (ValueError, TypeError):
                        raise ValueError(f"argument '{arg}' must be a {t}")
        return out

    def dispatch(self, name: str, arguments: dict | None = None) -> FunctionResult:
        t0 = time.perf_counter()
        spec = self._specs.get(name)
        if spec is None:
            return FunctionResult(name, False, error=f"unknown function: {name}")
        try:
            args = self._validate(spec, arguments or {})
            result = spec.func(**args)
        except Exception as exc:                                      # noqa: BLE001
            return FunctionResult(name, False, error=f"{type(exc).__name__}: {exc}",
                                  latency_ms=round((time.perf_counter() - t0) * 1000, 2))
        return FunctionResult(name, True, result=result,
                              latency_ms=round((time.perf_counter() - t0) * 1000, 2))

    def call(self, fc: FunctionCall) -> FunctionResult:
        return self.dispatch(fc.name, fc.arguments)
