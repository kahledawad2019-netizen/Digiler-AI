"""Safety sandbox for the code-execution tools (defensive).

``SafeCalculator`` evaluates arithmetic via a strict AST whitelist (numbers +
operators only — no names, calls, attributes). ``SafePython`` runs a restricted
subset: it AST-validates the code (no imports, no dunder attributes, no dangerous
builtins), executes it in a namespace whose ``__builtins__`` is a small safe set,
and enforces a wall-clock timeout in a worker thread. This blocks the usual escape
paths (``__import__``/``eval``/``open``/attribute walks, infinite loops). It is a
defence-in-depth guard, not a substitute for OS-level isolation — noted honestly.
"""

from __future__ import annotations

import ast
import io
import math
from contextlib import redirect_stdout


class UnsafeCodeError(ValueError):
    pass


# -- calculator ------------------------------------------------------------- #
_CALC_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Load,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
               ast.USub, ast.UAdd)


class SafeCalculator:
    def eval(self, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise UnsafeCodeError(f"invalid expression: {exc}") from exc
        for node in ast.walk(tree):
            if not isinstance(node, _CALC_NODES):
                raise UnsafeCodeError(f"disallowed in calculator: {type(node).__name__}")
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                raise UnsafeCodeError("only numeric constants allowed")
        return eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})  # noqa: S307


# -- restricted python ------------------------------------------------------ #
_SAFE_BUILTINS = {name: getattr(__builtins__, name, None) if not isinstance(__builtins__, dict)
                  else __builtins__.get(name)
                  for name in ("abs", "min", "max", "sum", "len", "round", "range", "sorted",
                               "enumerate", "zip", "map", "filter", "list", "dict", "set",
                               "tuple", "str", "int", "float", "bool", "print", "reversed",
                               "any", "all", "divmod", "pow")}
_SAFE_MATH = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
_FORBIDDEN_NAMES = {"__import__", "eval", "exec", "compile", "open", "input", "globals",
                    "locals", "vars", "getattr", "setattr", "delattr", "hasattr", "__builtins__",
                    "breakpoint", "memoryview", "help", "exit", "quit"}
_FORBIDDEN_NODES = (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Lambda,
                    getattr(ast, "AsyncFunctionDef", ast.FunctionDef), getattr(ast, "Await", ast.AST))


def _validate_python(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise UnsafeCodeError("imports are not allowed")
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            raise UnsafeCodeError("global/nonlocal not allowed")
        if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
            raise UnsafeCodeError(f"dunder attribute access not allowed: {node.attr}")
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise UnsafeCodeError(f"forbidden name: {node.id}")


class SafePython:
    def __init__(self, timeout: float = 2.0) -> None:
        self.timeout = timeout

    def run(self, code: str) -> dict:
        import sys
        import threading
        import time

        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise UnsafeCodeError(f"syntax error: {exc}") from exc
        _validate_python(tree)

        ns = {"__builtins__": {k: v for k, v in _SAFE_BUILTINS.items() if v is not None},
              "math": type("m", (), _SAFE_MATH)}
        out = io.StringIO()
        holder: dict = {}
        deadline = time.perf_counter() + self.timeout

        def _tracer(frame, event, arg):                              # aborts a runaway snippet
            if time.perf_counter() > deadline:
                raise TimeoutError(f"execution timed out after {self.timeout}s")
            return _tracer

        def _exec() -> None:
            sys.settrace(_tracer)
            try:
                with redirect_stdout(out):
                    exec(compile(tree, "<sandbox>", "exec"), ns, ns)  # noqa: S102
                holder["result"] = ns.get("result")
            except Exception as exc:                                  # noqa: BLE001
                holder["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                sys.settrace(None)

        th = threading.Thread(target=_exec, daemon=True)
        th.start()
        th.join(self.timeout + 1.0)
        if th.is_alive() or "error" in holder:                       # timed out or raised
            raise UnsafeCodeError(holder.get("error", f"execution timed out after {self.timeout}s"))
        return {"stdout": out.getvalue().strip(), "result": holder.get("result")}
