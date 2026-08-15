# Stage 24 — Function Calling

A safe, **schema-described tool surface** an LLM (or the Coordinator) can call — the
runtime that turns a `{name, arguments}` request into a validated, sandboxed
execution through the **existing controllers**. The Stage-22 Tool registry is the
single source of truth for each capability; this stage adds JSON argument schemas, a
validating dispatcher, new safe tools, and a genuine **safety sandbox**. Fully
additive. Package: [`src/ala/functions/`](../src/ala/functions/).

## The catalog (10 tools)

| tool | routed through | safe? |
|---|---|---|
| `calculator` | AST-whitelist arithmetic | sandbox |
| `python` | AST-validated restricted exec + timeout | sandbox |
| `search` | GraphRAG (grounded, cited) | read-only |
| `planner` | Study Planner | read-only |
| `quiz` | Quiz gen + RL difficulty | read-only |
| `web_search` | Web Search | read-only |
| `pdf` | pypdf text extraction | read-only |
| `video` | Video Adapter transcribe | read-only |
| `calendar` | Study Planner → iCalendar (.ics) | read-only |
| `knowledge_update` | Incremental Ingestor | **mutating, gated** |

Every service-backed tool reuses the exact Stage-22 tool (one retrieval path, one
ingestion path). `knowledge_update` is the only mutating tool and is policy-gated
(`tools.allow_knowledge_update`).

## Safety sandbox ([safety.py](../src/ala/functions/safety.py))

- **`SafeCalculator`** — parses with `ast.parse(mode="eval")` and permits only
  numeric constants + arithmetic operators; any `Name`/`Call`/`Attribute` is rejected.
- **`SafePython`** — AST-validates (no imports, no dunder attributes, no dangerous
  builtins like `eval`/`open`/`__import__`/`globals`), executes in a namespace whose
  `__builtins__` is a small safe set (+ a read-only `math`), and enforces a wall-clock
  **timeout via a trace-based deadline** that *stops* a runaway loop (no lingering
  thread). This blocks the standard escapes; it is defence-in-depth, **not** OS-level
  isolation (a hostile payload should still run in a container/seccomp jail in prod).

## Dispatcher ([registry.py](../src/ala/functions/registry.py))

`dispatch(name, args)` validates arguments against the tool's schema (required
present, unknown args rejected, basic type coercion), executes the tool, catches any
error and returns a structured `FunctionResult(ok, result, error, latency_ms)` — a
safe boundary that never raises at the caller.

## CLI

```powershell
ala functions --list                                   # JSON tool schemas (LLM-ready)
ala functions calculator --arg "expression=2*(3+4)**2"
ala functions search --arg "question=what is a foreign key"
ala functions --benchmark
```

## Benchmark (real tools + real safety — no mocks) — `reports/stage23_functions/`

| metric | value |
|---|---|
| tools (schema-described) | **10** (schemas valid) |
| **attacks blocked** | **10/10 (1.00)** — imports, `open`, `eval`, `__import__`, dunder walks, `globals()`, infinite loop |
| valid dispatch success | **8/8 (1.00)** — calc `2*(3+4)**2`→98, python `sum(i*i…)`→285, search 64 ms, quiz 148 ms, pdf 433 ms, calendar (.ics) |
| malformed calls rejected | **4/4** (missing required, unknown arg, unknown function, bad type) |

## Visualizations

`tool_catalog` (safe vs mutating) · `safety` (blocked / succeeded / rejected) ·
`dispatch_latency`.

## Tests

[`tests/test_functions.py`](../tests/test_functions.py) — calculator eval + blocking,
python safe execution + **attack blocking** + **timeout stops a runaway loop with no
leaked thread**, schema + dispatch + argument validation (coercion / missing / unknown
/ bad type), iCalendar export, and a real-corpus integration test. Full suite
**224 passed**.

## Limitations (honest)

- The sandbox is defence-in-depth, not a jail — production should still isolate
  untrusted code at the OS level (container / seccomp / resource limits).
- A router mapping natural language → function calls is a thin layer on top (rule- or
  LLM-based); this stage delivers the safe, schema-described **execution runtime**.
- `video`/`pdf` tools require the file/URL to be reachable; `web_search` is disabled
  unless a provider is configured (Stage 14).

## Extension hooks

- **LLM tool-use loop:** feed `registry.schemas()` to an LLM (via the Stage-12
  `OpenAICompatibleLLM` seam); execute the returned tool calls through `dispatch`.
- **New tools** register as one more `FunctionSpec` wrapping an existing service.
- **Calendar / notifications** integrate the `.ics` export with a real calendar.
