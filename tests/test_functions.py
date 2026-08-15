"""Stage 23 — Function Calling tests (safety sandbox + registry + real integration)."""

from __future__ import annotations

import pytest

from ala.config.settings import load_settings
from ala.functions.models import FunctionSpec
from ala.functions.registry import FunctionRegistry
from ala.functions.safety import SafeCalculator, SafePython, UnsafeCodeError


# -- calculator sandbox ----------------------------------------------------- #
def test_calculator_evaluates_and_blocks():
    c = SafeCalculator()
    assert c.eval("2 * (3 + 4) ** 2") == 98
    assert c.eval("10 // 3 + 1") == 4
    for attack in ['__import__("os")', 'open("x")', "1 + len([1])", "x + 1"]:
        with pytest.raises(UnsafeCodeError):
            c.eval(attack)


# -- python sandbox --------------------------------------------------------- #
def test_python_runs_safe_code():
    py = SafePython(timeout=1.0)
    assert py.run("result = sum(i*i for i in range(10))")["result"] == 285
    assert py.run("print('hi')\nresult = math.sqrt(16)")["result"] == 4.0


def test_python_blocks_attacks():
    py = SafePython(timeout=1.0)
    attacks = ["import os", "from os import system", 'open("/etc/passwd")', 'eval("1")',
               "().__class__.__bases__[0].__subclasses__()", '__import__("os")', "globals()",
               "getattr(1, 'real')"]
    for a in attacks:
        with pytest.raises(UnsafeCodeError):
            py.run(a)


def test_python_timeout_stops_runaway():
    import threading
    before = threading.active_count()
    with pytest.raises(UnsafeCodeError):
        SafePython(timeout=0.4).run("while True:\n    x = 1")
    assert SafePython(timeout=1.0).run("result = 6*7")["result"] == 42     # recovers
    assert threading.active_count() <= before + 1                          # no runaway thread left


# -- registry --------------------------------------------------------------- #
def _calc_registry() -> FunctionRegistry:
    reg = FunctionRegistry()
    c = SafeCalculator()
    reg.register(FunctionSpec("calculator", "arithmetic", lambda expression: {"value": c.eval(expression)},
                              {"expression": {"type": "string", "required": True}}))
    reg.register(FunctionSpec("add", "add two ints", lambda a, b: {"sum": a + b},
                              {"a": {"type": "integer", "required": True},
                               "b": {"type": "integer", "required": True}}))
    return reg


def test_registry_schema_and_dispatch():
    reg = _calc_registry()
    schemas = reg.schemas()
    assert any(s["name"] == "calculator" and "expression" in s["parameters"]["properties"]
               for s in schemas)
    r = reg.dispatch("calculator", {"expression": "3+4"})
    assert r.ok and r.result["value"] == 7 and r.latency_ms >= 0


def test_registry_validation():
    reg = _calc_registry()
    assert not reg.dispatch("calculator", {}).ok                  # missing required
    assert not reg.dispatch("calculator", {"expression": "1", "x": 2}).ok   # unknown arg
    assert not reg.dispatch("nope", {}).ok                        # unknown function
    added = reg.dispatch("add", {"a": "3", "b": "4"})             # string → int coercion
    assert added.ok and added.result["sum"] == 7
    assert not reg.dispatch("add", {"a": "x", "b": "4"}).ok       # bad type


# -- calendar --------------------------------------------------------------- #
def test_calendar_ics():
    from ala.functions.calendar import plan_to_ics
    from ala.planner.models import StudyActivity, StudyDay, StudyPlan
    plan = StudyPlan(goal="g", days=[
        StudyDay(1, [StudyActivity("read", "CNNs", "c1", 15), StudyActivity("quiz", "CNNs", "c1", 5)]),
        StudyDay(2, [StudyActivity("revision", "CNNs", "c1", 10)])])
    ics = plan_to_ics(plan)
    assert ics.startswith("BEGIN:VCALENDAR") and ics.count("BEGIN:VEVENT") == 2
    assert "SUMMARY:Study: CNNs" in ics


# -- real corpus ------------------------------------------------------------ #
def test_real_corpus_functions():
    settings = load_settings(None)
    from ala.graph.store import GraphStore
    loc = (settings.graph or {}).get("location", "data/graph/concept_graph.db")
    if not GraphStore(settings.abspath(loc)).exists():
        pytest.skip("concept graph not built")
    from ala.functions.service import FunctionService
    try:
        svc = FunctionService(settings)
    except FileNotFoundError:
        pytest.skip("retrieval artifacts not built")
    try:
        assert len(svc.schemas()) >= 9
        assert svc.call("calculator", expression="6*7").result["value"] == 42
        assert not svc.call("python", code="import os").ok                  # blocked
        qa = svc.call("search", question="what is gradient descent")
        assert qa.ok and "answer" in qa.result
    finally:
        svc.close()
