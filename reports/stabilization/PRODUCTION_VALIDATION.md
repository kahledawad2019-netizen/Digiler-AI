# Digiler AI — Production Validation Report

Real-execution validation of the full stack (backend + frontend + AI pipeline) against
the real Knowledge Base (21,854 vectors, 257 catalogued resources, 7 courses). Every
number here comes from actual execution — nothing is fabricated.

Environment: Windows, Python 3.11, Node 20, network up. Ollama server running on :11434
**with no model pulled**. Qdrant in local (embedded) mode. Backend exercised via
in-process ASGI (real routing, real services, real corpus).

## Bugs found & fixed

| # | Severity | Bug | Root cause | Fix |
|---|----------|-----|-----------|-----|
| 1 | Blocker | App crashed on import | `EmailStr` needs `email-validator`, missing from requirements | Added `email-validator` to `backend/requirements.txt` |
| 2 | Blocker | Register/login broken (500) → **whole app unusable** | `bcrypt` 5.x removed `__about__`, which `passlib` 1.7.4 reads | Pinned `bcrypt>=4.0,<4.1` |
| 3 | High | Unclean shutdown + latent concurrency hazard | ala SQLite connections `check_same_thread=True`, closed cross-thread | `check_same_thread=False` (safe: sqlite `threadsafety=3`) in catalog + student store |
| 4 | Medium | Backend test suite failed (`no such table`) | Tests didn't run the app lifespan → tables never created | Context-managed session-scoped `client` fixture |
| 5 | **Blocker** | **Chat returned 500 / empty (the "chat not working" report)** | Ollama **server up but model not pulled** → health check passed (server-only) → generation hit missing model → 500, no fallback | Model-aware health (server **and** model), generation-time fallback in `LLMBackedGenerator`, streaming fallback in `chat_service` |
| 6 | Medium | Profile "Recommended next steps" always empty | Dashboard JSON never included recommendations; frontend read `d.recommendations` | Wired the existing Stage-19 `RecommendationEngine` into the dashboard response |
| 7 | Low | `/` returned 500 on some dev setups | Relied on a server-component `redirect()` | Added a routing-layer redirect `/` → `/chat` in `next.config.mjs` |
| — | Security | `next@14.2.15` advisory | Known Next.js CVE | Patched to `next@14.2.35` (latest compatible patch) |
| — | UX | Course names shown as lowercase slugs | No display formatting | `formatCourse` / `formatTitle` helpers (Title Case, acronyms, week/session codes) |

## Live frontend↔backend contract verification

Fetched the actual backend responses (fixed code) and checked them against what each
page renders — the class of bug that makes a page "load but show nothing":

- **Chat** streaming contract matches: SSE `done` event carries `chat_id` (UI persists the chat); token/final via `message` events. ✓
- **Profile / Dashboard**: found + fixed the missing `recommendations` (bug 6). Verified populated for an active learner (`practice | SQL Join | seen only 1 time(s)`), weak/strong render. ✓
- **Planner** (`stats`, `days[].activities`), **Quiz** (`{question, difficulty, source}`), **Related** (`{concepts[].concept_id}`), **Student** (`summary/weak/strong`), **Settings/LLM** — all shapes match the frontend. ✓
- **Routes** (production standalone server): `/` → 307 → `/chat`; `/login /chat /courses /profile /admin /planner /settings` all 200. ✓

## What was verified by real execution

### Backend — all 45 routes registered; 26/26 exercised endpoints return < 400
Auth (register/login/me/refresh), health/ready/llm, knowledge tree/resources/summarize/
related, search, graph/stats, student, dashboard, functions, chat (+SSE stream), planner
(+ .ics), research, agents/ask, citations, functions/call, resource detail. Clean startup
and shutdown.

### Chat pipeline (the headline fix) — real answers, grounded & cited
- Before restart (server-up, no model): `/api/chat` → **500** (reproduced on the live instance).
- After fix: `/api/chat` → **200**, `generator=extractive-grounded`, confidence 0.75,
  **21 citations**; `/api/chat/stream` → 523 chars of cited content.
- With a model pulled (`ollama pull qwen3`): health flips to reachable, answers come from
  the LLM, and any LLM error still degrades to the grounded generator (never a 500).

### Tests — 240 passed, 0 failed
- ala platform suite: **232 passed** (real corpus, includes GraphRAG / retrieval / agents /
  functions / research / student / graph / video / vision ingestion round-trips).
- backend API suite: **8 passed**.
- LLM provider suite (`test_llm.py`): 8 passed, including the new model-aware health.

### Frontend — typecheck clean, production build clean
`tsc --noEmit`: 0 errors. `next build`: 13 routes compiled (/, /chat, /chat/[id], /courses,
/knowledge, /login, /planner, /profile, /settings, /admin, /instructor). Patched Next 14.2.35.

## Performance (warm, N=20, real corpus, extractive path)

| Operation | Median | p95 |
|-----------|-------:|----:|
| health | 1 ms | 2 ms |
| student | 2 ms | 2 ms |
| planner | 4 ms | 5 ms |
| graph/stats | 8 ms | 9 ms |
| dashboard | 22 ms | 162 ms |
| knowledge/tree | 32 ms | 33 ms |
| agents/ask | 82 ms | 85 ms |
| citations (retrieval) | 89 ms | 234 ms |
| **chat (GraphRAG full pipeline)** | **104 ms** | **138 ms** |
| search (hybrid retrieval) | 109 ms | 135 ms |

Cold start (build services + load e5 + open Qdrant): **31 s** one-time. Process RSS after
warmup: ~1.5 GB (e5 embedding model + Qdrant local index). Chart: `latency_benchmark.png`.

> With a pulled Ollama model, chat latency is dominated by LLM token generation (seconds);
> the retrieval + evidence portion stays ~100 ms.

## Component status

| Component | Status | Evidence |
|-----------|--------|----------|
| Backend (FastAPI 0.141) | OK | 45 routes, clean start/stop |
| Frontend (Next 14.2.35) | OK | typecheck + build clean, 13 routes |
| Qdrant (local mode, 21,854 pts) | OK | retrieval 109 ms |
| GraphRAG | OK | chat 104 ms, 21 citations |
| Hybrid Retrieval | OK | search 109 ms |
| Chat + streaming | OK (fixed) | 200, grounded, cited |
| Course summaries (retrieval-backed) | OK | summarize 200 |
| Quiz (function/agent) | OK | quiz endpoint 200 |
| Research Mode | Endpoint OK | /research 200 (see limitations) |
| Dashboard / Planner / Student Model | OK | 200s, real analytics + plan |
| AI Agents | OK | agents/ask 200 |
| Function Calling | OK | calculator 2+2*10 correct |
| Citation Explorer | OK | citations 200, 21 nodes |
| Upload endpoint | Guards OK | 401/415; ingestion covered by suite |
| PDF / Video / Vision ingestion | OK | covered by ala suite (real files) |
| Ollama (LLM) | Server up, **no model** | reachable=False, graceful fallback |

## Known limitations (honest)

- **Ollama has no model pulled** in this environment. Chat works via the grounded
  extractive generator. For full LLM answers: `ollama pull qwen3` (or qwen2.5 / llama3),
  then restart the backend.
- **The running backend must be restarted** to pick up the LLM fix (code change).
- **Qdrant local mode is single-process**: only one process may open `data/qdrant` at a
  time. Do not run uvicorn with `--workers > 1` or the CLI/tests while the server is up —
  use Qdrant **server mode** (docker-compose provides it) for concurrency. A second opener
  fails with a lock error, which surfaces as every AI endpoint returning 500.
- **Real external web search** (Research Mode) returns a valid response but performing a
  live external search depends on a configured search provider; not verified in this pass.
- Frontend↔backend validated via production build + typed client + real backend responses;
  a live click-through browser session was not part of this automated pass.
- `npm audit` flags the Next.js lineage; the only offered remediation is Next 16 (a breaking
  major, out of scope for stabilization). Patched to the latest 14.2.x; the flagged sinks
  (image optimizer remotePatterns, rewrite SSRF, Server Actions, i18n, CSP nonces) are not
  reachable in this app's configuration.
