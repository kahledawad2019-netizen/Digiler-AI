# Stage 23 — Function Calling: Benchmark

**10 schema-described tools**, all routed through the existing controllers. Schemas valid: True.

Tools: calculator, python, search, planner, quiz, web_search, pdf, video, calendar, knowledge_update

## Safety (calculator + python sandbox)
- **10/10 attacks blocked** (rate **1.0**); leaked: none.
- attacks include imports, `open`, `eval`, `__import__`, dunder walks, `globals()`, and an infinite loop (aborted by the timeout).

## Valid dispatch (real execution)
- success **8/8** (rate 1.0); calculator `2*(3+4)**2` → {'expression': '2 * (3 + 4) ** 2', 'value': 98}; python `sum(i*i…)` → {'stdout': '', 'result': 285}.

| tool | ok | latency ms | sample |
|---|---|---|---|
| calculator | True | 0.11 | {"expression": "2 * (3 + 4) ** 2", "value": 98} |
| python | True | 0.8 | {"stdout": "", "result": 285} |
| search | True | 64.38 | {"answer": "Key concepts: Convolutional Neural Network [K1], |
| planner | True | 2.47 | {"plan": {"goal": "master my weak concepts", "days": [{"day" |
| quiz | True | 147.78 | {"question": "Define the concept of 'concept:sql-join'.", "d |
| calendar | True | 3.15 | {"ics": "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Digiler |
| web_search | True | 0.02 | {"sources": []} |
| pdf | True | 433.47 | {"n_pages": 9, "chars": 1858, "text": "DIGILIANS\nO P E N I  |

## Argument validation
- **4/4** malformed calls rejected (missing required, unknown arg, unknown function, bad type) — rate 1.0.

## Figures (`figures/`)
`tool_catalog` · `safety` · `dispatch_latency`.

## Honest notes
- The sandbox is **defence-in-depth** (AST validation + restricted `__builtins__` + wall-clock timeout), which blocks the usual escapes; it is **not** OS-level isolation — a hostile payload should still run in a container/seccomp jail in production. The timeout aborts the watcher but a CPU-bound thread keeps running until process exit (daemon).
- `knowledge_update` is **mutating** and policy-gated (`tools.allow_knowledge_update`); it grows the KB through the existing ingestion pipeline only.
- A rule/LLM router mapping natural language → function calls is a thin layer on top; this stage delivers the safe, schema-described execution runtime.
