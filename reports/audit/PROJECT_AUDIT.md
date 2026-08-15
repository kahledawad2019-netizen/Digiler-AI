# Phase 1 — Project Audit (Digiler AI)

Evidence-based audit. Tags: **[verified]** = confirmed by real execution this project;
**[inspected]** = read the code; **[unverified]** = not yet exercised. No code was
modified in this phase.

## 0. Metrics

| Area | Size |
|------|------|
| ala platform (`src/ala`) | 243 Python files · ~21,600 LOC · 20+ subpackages |
| Backend (`backend/app`) | 35 files · ~1,660 LOC · 45 routes |
| Frontend (`frontend/src`) | 31 TS/TSX files · 11 routes · 1 store |
| Tests | 39 files · 232 platform + 8 backend = **240 tests** |
| Technical-debt markers | 5 TODO/FIXME in the whole ala package (excellent hygiene) |

## 1. Architecture

- **Baseline:** Architecture V3 (frozen). Clean layering: ala core (framework-free) →
  thin FastAPI backend → Next.js frontend. **[inspected]**
- **ala packages:** core, config, metadata, catalog, registry, fabric, context, ingestion,
  retrieval, graph, rag, research, student, dashboard, planner, rl, agents, functions, llm,
  video, vision, explorer. **[verified]** (all exercised by the 232-test suite)
- **Reuse discipline:** the backend is a genuine thin layer — one shared `AgentService`
  bundle, no business logic duplicated. **[verified]**

## 2. Component status

| Component | State | Evidence |
|-----------|-------|----------|
| Backend (FastAPI 0.141 / Starlette 1.3, async SQLAlchemy 2.0) | ✅ working | 45 routes, clean start/stop **[verified]** |
| Frontend (Next 14.2.35 App Router, TS, Tailwind, React Query, Zustand) | ✅ working | typecheck + build clean, 11 routes **[verified]** |
| Database — web state (SQLite dev / Postgres prod) | ✅ working | tables auto-create via lifespan **[verified]** |
| Vector store — Qdrant (21,854 vectors) | ✅ working (local mode) | retrieval ~109 ms **[verified]** |
| Auth — JWT access+refresh, bcrypt, RBAC (student/instructor/admin) | ✅ working | auth flow + role gates **[verified]** |
| RAG — GraphRAG + hybrid retrieval + evidence | ✅ working | chat ~104 ms, 21 citations **[verified]** |
| Embeddings — e5 (with hashing fallback) | ✅ working | loads at cold start (~1.5 GB RSS) **[verified]** |
| LLM — Ollama provider, model-aware health, extractive fallback | ✅ working | 200 grounded even with no model **[verified]** |
| Chat + SSE streaming | ✅ working | streamed cited content **[verified]** |
| Summaries (retrieval-backed) | ✅ working | `/knowledge/summarize` 200 **[verified]** |
| Quiz (single type) | ✅ working | `{question, difficulty, source}` **[verified]** |
| Semantic + hybrid search | ✅ working | `/search` 200 **[verified]** |
| Web Search (Research Mode, bilingual Wikipedia) | ✅ working | used_web=True, real sources **[verified]** |
| Planner (+ iCal) | ✅ working | day-by-day plan **[verified]** |
| Dashboard + recommendations | ✅ working | populated for active learner **[verified]** |
| Personalization (Student Model) | ✅ working | mastery/weak/strong/events **[verified]** |
| RL (LinUCB contextual bandit) | ✅ baseline | regret 0.167 vs fixed **[verified]** |
| Agents (7 + coordinator) | ✅ working | routing + study session **[verified]** |
| Citations / Citation Explorer | ✅ working | 21 nodes **[verified]** |
| Admin / Instructor panels | ✅ working | role-gated **[verified]** |

## 3. Existing vs missing features

**Existing (working):** chat+streaming, summaries, quiz (1 type), search, web search,
planner, dashboard, recommendations, progress tracking, agents, RL baseline, citations,
admin/instructor, bilingual (ar/en) retrieval + web search.

**Missing / planned:**
- **Quiz types** — only one type; no MCQ / True-False / short-answer / explanations / hints.
- **UI/UX product-grade redesign** — current design is clean but minimal.
- **Deeper agent strengthening** — adaptive tutor tone, follow-ups, multi-query research, re-ranking.
- **Caching / rate-limiting** for web search (Redis is provisioned but not in the request path).

**Broken:** none currently — the 7 bugs found earlier (login/bcrypt, email-validator,
chat-500 LLM, SQLite shutdown, test lifespan, dashboard recommendations, `/` redirect) are
all fixed and verified.

## 4. Dead code / duplication

- Very low debt (5 TODO/FIXME across 21.6k LOC). **[verified]**
- **Candidate duplication:** `retrieval/bm25/tokenizer.py` and `retrieval/chunking/tokenizer.py`
  — review whether they can share one implementation. **[inspected — needs review]**
- No obvious dead modules (all packages are imported/tested).

## 5. Performance bottlenecks **[verified]**

- **Cold start ~31 s** (one-time: e5 model load + open Qdrant with 21,854 points).
- **Process RSS ~1.5 GB** (dominated by the e5 model + Qdrant local index).
- **Qdrant local mode is single-process** — only one process may open `data/qdrant`; blocks
  uvicorn `--workers > 1` and concurrent CLI. Needs **Qdrant server mode** for concurrency.
- Warm latencies are good (chat 104 ms, search 109 ms, dashboard 22 ms).

## 6. Security issues

| Severity | Issue | Detail |
|----------|-------|--------|
| **Critical** | **Committed OAuth `client_secret`** | Google OAuth secret JSON is **git-tracked** in 3 paths (`KNOWLEDGE BASE/…`, `Basic_knowladg/…`, `knowledge_base/_quarantine/…`). Must be purged from history + the credential **rotated**. **[verified]** |
| High | **Minimal `.gitignore`** | Only `.venv/` + `__pycache__/`. `.env`, `*.db`, `node_modules/`, `.next/`, `data/qdrant/` are **not** ignored → risk of committing secrets/data. **[verified]** |
| High | **Databases tracked in VCS** | `data/student/student.db`, `data/catalog/knowledge_catalog.db` are tracked (learner data in git). **[verified]** |
| Medium | Default secret key | `DIGILER_SECRET_KEY` defaults to `change-me…` — must be set in prod. **[inspected]** |
| Medium | Next.js advisory | Patched to 14.2.35; residual `npm audit` noise (fix = Next 16, breaking; out of scope). **[verified]** |
| Low | Input validation | Pydantic v2 validates request bodies; SQLAlchemy ORM (no raw SQL) → SQL-injection surface low. **[inspected]** |

## 7. UX problems

- **Course names were lowercase slugs** — fixed (Title Case). **[verified]**
- **`/` returned 500** on some dev setups — fixed (routing-layer redirect). **[verified]**
- **Design is minimal, not product-grade** — the main UX gap; the target of the redesign phase.
- No dark mode, limited empty/loading states, limited accessibility polish. **[inspected]**

## 8. State management & routing **[inspected]**

- **Routing:** Next App Router; `(app)` group is auth-guarded; `/` → `/chat`.
- **State:** Zustand (`auth` store, persisted tokens) + React Query (server state) + axios
  interceptors (Bearer + transparent refresh on 401). Clean, idiomatic.

## 9. How the audit maps to the remaining phases

Several later phases are **already substantially done** — do not redo blindly:

| Phase | Status going in |
|-------|-----------------|
| 2 Bug fixing | Mostly done (7 bugs fixed + verified); re-check after each new change |
| 3 UI/UX redesign | **Not started — the largest remaining item** |
| 4 AI improvements | Agents work; strengthening (adaptive/follow-ups/re-rank) pending |
| 5 Web search | **Done** (Wikipedia, bilingual, env config) — add caching/rate-limit |
| 6 Personalization | Working; verify updates per interaction |
| 7 Quiz system | **Not started** (MCQ/TF/short/explanations) |
| 8 Planner | Working; add dynamic re-planning |
| 9 RL | Working baseline (LinUCB) + design documented |
| 10 Performance | Measured; optimize cold start / Qdrant server mode |
| 11 Security | **Purge committed secret + fix `.gitignore` + untrack DBs** (highest priority) |
| 12 Final QA | Continuous (240 tests green) |

## 10. Recommended remediation order (priority)

1. **Security (Phase 11 pulled forward):** purge the committed `client_secret`, rotate it,
   expand `.gitignore`, untrack the databases. This is the only *critical* finding.
2. **Quiz system (Phase 7)** and **UI/UX redesign (Phase 3)** — the two biggest feature gaps.
3. **AI strengthening (Phase 4)**, web-search caching (Phase 5), performance (Phase 10).

## Verification of this phase

This audit is grounded in real execution from prior work (240 passing tests, every endpoint
exercised, a performance benchmark, live web-search validation) plus fresh read-only scans
(metrics, secrets, debt markers, structure). No code was modified. **Phase 1 complete.**
