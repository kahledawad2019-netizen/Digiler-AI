"""Stage 23 — Function-Calling benchmark (real tools + real safety, no mocks).

Measures the registry (schema-described tools), valid dispatch success (each tool
executed for real through its existing service), **safety** (an attack set against
the calculator/python sandbox must be fully blocked), argument validation, and
latency. The single retrieval/ingestion paths are reused — no duplication.
"""

from __future__ import annotations

import json
from pathlib import Path

from ala.config.settings import Settings
from ala.functions.service import FunctionService

_ATTACKS = [
    ("calculator", {"expression": '__import__("os").system("echo hi")'}),
    ("calculator", {"expression": 'open("/etc/passwd")'}),
    ("python", {"code": "import os"}),
    ("python", {"code": "from os import system"}),
    ("python", {"code": 'open("/etc/passwd").read()'}),
    ("python", {"code": "().__class__.__bases__[0].__subclasses__()"}),
    ("python", {"code": 'eval("2+2")'}),
    ("python", {"code": '__import__("os").system("echo hi")'}),
    ("python", {"code": "globals()"}),
    ("python", {"code": "while True:\n    x = 1"}),        # infinite loop → timeout
]


def run_functions_benchmark(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage23_functions")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    svc = FunctionService(settings)
    try:
        svc.services.graphrag.answer("warmup", top_k=5)
        concept = _a_concept(svc)
        pdf_path = _a_pdf(settings)

        valid = [
            ("calculator", {"expression": "2 * (3 + 4) ** 2"}),
            ("python", {"code": "result = sum(i*i for i in range(10))"}),
            ("search", {"question": "what is a convolutional neural network"}),
            ("planner", {"student_id": "fn-demo", "days": 7, "minutes": 45}),
            ("quiz", {"concept": concept, "student_id": "fn-demo"}),
            ("calendar", {"student_id": "fn-demo", "days": 7}),
            ("web_search", {"query": "transformers"}),
        ]
        if pdf_path:
            valid.append(("pdf", {"path": pdf_path, "max_chars": 500}))

        valid_results = [(n, svc.call(n, **a)) for n, a in valid]
        attack_results = [(n, svc.call(n, **a)) for n, a in _ATTACKS]
        invalid = [
            ("calculator", {}),                            # missing required
            ("search", {"question": "x", "bogus": 1}),     # unknown arg
            ("nope", {}),                                  # unknown function
            ("planner", {"days": "not-a-number"}),         # bad type
        ]
        invalid_results = [(n, svc.call(n, **a)) for n, a in invalid]

        n_valid = sum(r.ok for _n, r in valid_results)
        n_blocked = sum(not r.ok for _n, r in attack_results)
        n_rejected = sum(not r.ok for _n, r in invalid_results)
        payload = {
            "n_functions": len(svc.registry.names()),
            "functions": svc.registry.names(),
            "schemas_valid": all("parameters" in s and "name" in s for s in svc.schemas()),
            "valid_dispatch": {"n": len(valid_results), "succeeded": n_valid,
                               "success_rate": round(n_valid / len(valid_results), 3),
                               "results": [{"name": n, "ok": r.ok, "latency_ms": r.latency_ms,
                                            "sample": _sample(r)} for n, r in valid_results]},
            "safety": {"n_attacks": len(attack_results), "blocked": n_blocked,
                       "blocked_rate": round(n_blocked / len(attack_results), 3),
                       "leaked": [n for n, r in attack_results if r.ok]},
            "validation": {"n": len(invalid_results), "rejected": n_rejected,
                           "rejection_rate": round(n_rejected / len(invalid_results), 3)},
            "latency_ms": {n: r.latency_ms for n, r in valid_results if r.ok},
            "example_calc": next((r.result for n, r in valid_results if n == "calculator"), None),
            "example_python": next((r.result for n, r in valid_results if n == "python"), None),
        }
    finally:
        svc.close()

    (out / "functions.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str),
                                        encoding="utf-8")
    from ala.functions import viz
    viz.render_all(payload, figs)
    (out / "FUNCTIONS.md").write_text(_markdown(payload), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
def _a_concept(svc) -> str:
    from ala.graph.models import NodeType
    from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
    g = svc.services.graph
    for cid in g.nodes(NodeType.CONCEPT.value):
        if any(nb.startswith("resource:") for nb, _e, _d in g.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES)):
            return cid
    return "concept:cnn"


def _a_pdf(settings) -> str | None:
    for p in sorted(settings.raw_path.rglob("*.pdf"))[:1]:
        return str(p)
    return None


def _sample(r) -> str:
    if not r.ok:
        return r.error or ""
    s = json.dumps(r.result, default=str)
    return s[:90]


def _markdown(p: dict) -> str:
    vd, sf, val = p["valid_dispatch"], p["safety"], p["validation"]
    rows = "\n".join(f"| {x['name']} | {x['ok']} | {x['latency_ms']} | {x['sample'][:60]} |"
                     for x in vd["results"])
    return "\n".join([
        "# Stage 23 — Function Calling: Benchmark",
        "",
        f"**{p['n_functions']} schema-described tools**, all routed through the existing controllers. "
        f"Schemas valid: {p['schemas_valid']}.",
        "",
        f"Tools: {', '.join(p['functions'])}",
        "",
        "## Safety (calculator + python sandbox)",
        f"- **{sf['blocked']}/{sf['n_attacks']} attacks blocked** (rate **{sf['blocked_rate']}**); "
        f"leaked: {sf['leaked'] or 'none'}.",
        f"- attacks include imports, `open`, `eval`, `__import__`, dunder walks, `globals()`, and an "
        "infinite loop (aborted by the timeout).",
        "",
        "## Valid dispatch (real execution)",
        f"- success **{vd['succeeded']}/{vd['n']}** (rate {vd['success_rate']}); "
        f"calculator `2*(3+4)**2` → {p['example_calc']}; python `sum(i*i…)` → {p['example_python']}.",
        "",
        "| tool | ok | latency ms | sample |",
        "|---|---|---|---|",
        rows,
        "",
        "## Argument validation",
        f"- **{val['rejected']}/{val['n']}** malformed calls rejected (missing required, unknown arg, "
        f"unknown function, bad type) — rate {val['rejection_rate']}.",
        "",
        "## Figures (`figures/`)",
        "`tool_catalog` · `safety` · `dispatch_latency`.",
        "",
        "## Honest notes",
        "- The sandbox is **defence-in-depth** (AST validation + restricted `__builtins__` + wall-clock "
        "timeout), which blocks the usual escapes; it is **not** OS-level isolation — a hostile payload "
        "should still run in a container/seccomp jail in production. The timeout aborts the watcher but a "
        "CPU-bound thread keeps running until process exit (daemon).",
        "- `knowledge_update` is **mutating** and policy-gated (`tools.allow_knowledge_update`); it grows "
        "the KB through the existing ingestion pipeline only.",
        "- A rule/LLM router mapping natural language → function calls is a thin layer on top; this stage "
        "delivers the safe, schema-described execution runtime.",
        "",
    ])
