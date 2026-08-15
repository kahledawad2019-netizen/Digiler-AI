# Production Milestone P1 — Backend API (thin layer over the platform)

The first production milestone: a FastAPI backend that **exposes every implemented
capability without re‑implementing any of it**, plus the LLM provider that makes
answers fluent. Additive — the `ala` platform (Stages 1‑24) is unchanged except two
small additive enhancements (LLM provider integration point; Qdrant server‑URL
support).

## Reuse, not rebuild

The backend calls the existing service classes and never duplicates their logic:

| endpoint area | reuses (existing) |
|---|---|
| chat / search / knowledge summarize | `GraphRAGService` (+ Ollama streaming) |
| citations | `CitationExplorer` / `CitationResolver` |
| research (confidence‑gated web) | `ResearchModeController` + `ConfidenceEstimator` |
| student / dashboard | `StudentModel`, `DashboardService` |
| planner / calendar | `StudyPlanner`, function `calendar` (iCalendar) |
| agents | `AgentService` (Tutor/Quiz/Evaluator/Planner/Research/Curator) |
| function calling | `FunctionRegistry` + `build_functions` (safe sandbox) |
| graph viz | `ConceptGraph` |
| upload | `IncrementalIngestor` / `VideoIngestor` (full pipeline) |

The reuse bridge is `app/deps/services.py::AlaServices` — it builds **one** shared
bundle (Qdrant locks its path, so a single GraphRAG/retrieval stack per process) and
every router shares it; the function registry, dashboard and citation explorer are
constructed over the **same** handles.

## LLM — Ollama provider (`ala.llm`)

A real provider abstraction over the existing Stage‑12 `LLMClient` seam:
`OllamaProvider` (HTTP `/api/chat` + health, complete/chat/**stream**), config‑driven
(**default Qwen3**, switch via `platform.yaml`/`ALA_LLM_MODEL`), supporting
qwen3/qwen2.5/llama3/mistral/gemma. `make_generator` returns the LLM‑backed generator
when Ollama is reachable, else the offline **extractive‑grounded** generator — so
`GraphRAGService`, agents and function‑calling all get fluent answers when Ollama is
up and never hard‑fail when it is down. **8 tests** (request build/parse/stream/
health/factory/fallback), no live server needed (injected transport). CLI `ala llm`.

## Structure (`backend/`)

```
app/main.py                 app factory (CORS, middleware, lifespan)
app/core/                   config · security (JWT/bcrypt) · middleware/errors
app/db/ · app/models/       async SQLAlchemy 2.0 (SQLite dev / Postgres prod)
app/schemas/                pydantic v2
app/deps/services.py        the single shared ala-services bridge
app/deps/auth.py            current-user + RBAC
app/api/routers/*.py        thin routers (health/auth/llm/chat/search/knowledge/
                            research/student/dashboard/planner/agents/functions/
                            graph/citations/upload)
app/services/chat_service   GraphRAG + Ollama streaming + confidence gate
tests/test_api.py           health + auth flow (SQLite)
```

## Validation performed (offline env)

The backend deps (`fastapi/uvicorn/sqlalchemy/…`) can't be installed in this offline
dev box, so the API can't be executed here. What **was** verified: every backend file
compiles; **every `ala` API the routers call exists with a matching signature**
(contract‑checked against the live platform); the catalog access returns the expected
257 resources with `metadata_json`; and the full platform suite stays green
(**232 passed**) after the two additive platform changes. The user runs the FastAPI
tests (`cd backend && pytest`) and `uvicorn` on a machine with the deps installed.

## Deployment

`docker-compose.yml` (postgres · redis · qdrant · ollama · backend · nginx),
`backend/Dockerfile`, `deploy/nginx/nginx.conf` (SSE‑aware proxy), `.github/workflows/
ci.yml` (platform tests · backend api tests · docker build), Alembic scaffolding.
`docker compose up` brings up the stack; the DB and LLM model are env‑switchable with
zero code changes.

## Honest limitations

- Not runnable/tested in this offline dev box (deps not installable); validated by
  compile + contract checks + the platform suite. The user validates the running API.
- Concurrent uploads while chatting require **Qdrant server mode** (compose provides
  it); local‑path mode is single‑process.
- The **frontend (Next.js)** is the next milestone — it consumes these endpoints.
