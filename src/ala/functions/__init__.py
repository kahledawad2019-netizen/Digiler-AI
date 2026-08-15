"""Stage 23 — Function Calling.

A safe, schema-described tool surface an LLM (or the Coordinator) can call:
calculator · python (sandboxed) · search / QA · knowledge-update · planner · quiz
· web-search · pdf · video · calendar. Every capability is **routed through the
existing controllers** (the Stage-22 Tool registry is the single source of truth);
this stage adds JSON argument schemas, a validating dispatcher, and a genuine
**safety sandbox** (AST validation + restricted namespace + timeout) for the
code-execution tools. Fully additive.
"""

from ala.functions.models import FunctionCall, FunctionResult, FunctionSpec
from ala.functions.registry import FunctionRegistry
from ala.functions.safety import SafeCalculator, SafePython, UnsafeCodeError
from ala.functions.service import FunctionService

__all__ = ["FunctionService", "FunctionRegistry", "FunctionSpec", "FunctionCall",
           "FunctionResult", "SafeCalculator", "SafePython", "UnsafeCodeError"]
