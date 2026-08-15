# Digiler AI — Backend (FastAPI)

A **thin transport/auth/persistence/streaming layer** over the existing `ala`
platform. Every capability (chat/GraphRAG, retrieval, knowledge base, research,
planner, dashboard, student model, agents, function‑calling, citations, video,
vision) is served by calling the already‑implemented `ala` services — **no business
logic is re‑implemented here.**

## Run locally (zero infra — SQLite + optional Ollama)

```bash
# from the repo root
pip install -e .                        # the ala platform
pip install -r backend/requirements.txt
cd backend && cp .env.example .env

# (optional) fluent LLM answers: install Ollama, then
ollama pull qwen3                       # or qwen2.5 / llama3 / mistral / gemma

uvicorn app.main:app --reload           # http://localhost:8000/docs
pytest -q                               # health + auth tests (SQLite)
```

Without Ollama running, chat still works — it falls back to the grounded
**extractive** generator (no hallucination). Start Ollama and answers become fluent
automatically; switch models with `ALA_LLM_MODEL=llama3` (zero code changes).

## Run the full stack (Docker)

```bash
docker compose up            # postgres · redis · qdrant · ollama · backend · nginx
docker compose exec ollama ollama pull qwen3
# API at http://localhost/api  ·  docs at http://localhost/docs
```

For Docker (and any concurrent‑ingestion setup) set the vector store to **server
mode** in `config/platform.yaml`:

```yaml
retrieval:
  vector_store:
    location: "http://qdrant:6333"     # was: data/qdrant  (local single-process)
```

## Endpoints (all under `/api`)

| area | routes |
|---|---|
| auth | `POST /auth/register` `/auth/login` `/auth/refresh` `GET /auth/me` |
| chat | `POST /chat` · `POST /chat/stream` (SSE) · `GET /chats` `/chats/{id}` · `DELETE /chats/{id}` |
| knowledge | `GET /knowledge/tree` `/resources` `/resource/{id}` · `POST …/summarize` `…/quiz` · `GET …/related` `…/citations` |
| search | `GET /search?q=` (resources + concepts + evidence) |
| research | `POST /research` (confidence‑gated; `save:true` grows the KB) |
| student | `GET /student` · `PUT /student/preferences` |
| dashboard | `GET /dashboard` |
| planner | `POST /planner` · `GET /planner/calendar` (.ics) |
| agents | `POST /agents/ask` `/agents/session` |
| functions | `GET /functions` · `POST /functions/call` |
| graph | `GET /graph/stats` `/graph/concept/{id}` |
| citations | `POST /citations` |
| upload | `POST /upload` (→ full ingestion) · `GET /uploads` |
| llm / health | `GET /llm` · `GET /health` `/ready` |

## Auth & roles

JWT access + refresh (`python-jose`), bcrypt hashing (`passlib`), roles
`student | instructor | admin`. Mutating function‑calls (`knowledge_update`) and
uploads require an authenticated user; `knowledge_update` requires instructor/admin.

## Notes (honest)

- **One shared service bundle:** Qdrant local mode locks its path, so the backend
  builds a single `AgentService` bundle (one GraphRAG/Qdrant) and every router reuses
  it. Concurrent uploads while chatting need **Qdrant server mode** (compose provides
  it).
- **DB is config‑driven:** SQLite for dev (default), PostgreSQL for prod via
  `DIGILER_DATABASE_URL` — zero code changes. Vectors never live in SQL (Qdrant only).
- **Migrations:** dev auto‑creates tables; prod uses Alembic —
  `alembic revision --autogenerate -m "init" && alembic upgrade head`.
- **Frontend:** the Next.js app is the next milestone; it consumes these endpoints.
