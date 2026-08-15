# Production Readiness Audit — Digiler AI

Adversarial self-review. Every claim is backed by real execution against the real corpus
with **Ollama Qwen3 active**. Weaknesses are stated plainly, not hidden.

---

## Phase 1 — Architecture Review (why each change was right/wrong)

| Change | Previous was wrong because… | New is correct because… | Trade-off / remaining limit |
|--------|------------------------------|--------------------------|------------------------------|
| **Retrieval-only for search/citations/quiz** | Called `answer_with_context` (full LLM gen) then **discarded** the answer → 20–40 s wasted per call | Use `merger.merge` — the evidence package with no generation (60–260 ms) | None functional; the answer was never used |
| **Streaming summarize/chat (SSE)** | Sync generation blocked 20–40 s → proxy reset | Headers flush at **0.23 s**, body streams with pings → reset-proof | First token still gated by LLM latency |
| **LLM model-aware health + fallback** | Health checked only that the server was up → 500 when the model wasn't pulled | Verifies the model is pulled; any LLM error degrades to grounded extractive | Extractive answers are less fluent than the LLM |
| **SQLite `check_same_thread=False`** | Cross-thread close crashed on shutdown + concurrency hazard | Safe under sqlite `threadsafety=3` (serialized) | Still single local file; not for multi-node |
| **bcrypt pin / email-validator** | Missing/incompatible deps broke login + import | Correct pins → auth works | Must keep pins current |
| **Dashboard recommendations wired** | Endpoint never returned `recommendations` the UI read | Reuses the existing RecommendationEngine | — |
| **Web search = Wikipedia (MediaWiki API)** | Provider defaulted to `disabled`; DuckDuckGo HTML is bot-blocked | Reliable, no-key, bilingual default; env-config for Tavily/Google | Wikipedia-only breadth unless an API key is set |
| **Upload filename sanitisation** | `dest_dir / file.filename` allowed `../` path traversal | `_safe_name` strips dirs + allowlist chars | — |

## Phase 2 — Production Verification (run, not assumed) — 17/17 PASS

Backend startup ✓ · register/login/JWT/refresh ✓ · DB write ✓ · Ollama (qwen3) reachable ✓
· knowledge tree (7 courses) ✓ · search/retrieval/vector/embeddings (8 evidence) ✓ · graph ✓
· quiz ✓ · citations ✓ · student model ✓ · dashboard+recommendations ✓ · planner ✓
· invalid resource→404 ✓ · **chat streaming (SSE)** ✓ · **summary streaming (SSE)** ✓
· invalid login→401 ✓. **Demo flow (Phase 7) runs end-to-end with no manual fixes.**

## Phase 3 — Performance

| Metric | Value |
|--------|-------|
| Cold start (services + e5 + Qdrant) | **10.6 s** |
| Memory RSS | 78 MB → **1.5 GB** warm (e5 model + Qdrant index) |
| Warm median / p95 (N=15) | health 1/1 · search 100/126 · quiz 66/83 · citations 75/82 · dashboard 22/35 · planner 3/4 ms |
| **Retrieval latency** | **~73 ms** |
| **Generation latency (Qwen3)** | **~20 s** (chat), ~40 s (summary) |
| Streaming time-to-headers | **0.23 s** (real uvicorn) |

**Bottleneck: 100% the local LLM.** Retrieval is sub-100 ms; Qwen3 generation is ~20 s and
dominates every generative response. This is inherent to local inference, not the architecture.

## Phase 4 — Failure Testing — 9/9 graceful

Ollama unavailable → health=False, chat degrades to **extractive (200, no crash)** ✓ ·
chat/stream still returns ✓ · irrelevant query → graceful 200 (nearest-neighbour evidence) ✓ ·
invalid resource → 404 JSON ✓ · invalid login → 401 ✓ · malformed body → 422 ✓ · no token → 401 ✓ ·
quiz works with Ollama down (129 ms) ✓.

**Not directly exercised (reasoned):** DB unavailable → fail-fast at startup (acceptable);
corrupted embeddings/Qdrant → structured JSON 500 via middleware (not graceful, but no reset);
network interruption → client `AbortController` + SSE disconnect; LLM timeout (120 s) → extractive.

## Phase 5 — Security Review

| Severity | Finding | Status |
|----------|---------|--------|
| **CRITICAL** | Google OAuth `client_secret_*.json` **committed to git** (3 paths) | **OPEN** — purge from history + **rotate the credential** (needs Google Console) |
| High | Upload path traversal (`../` filename) | **FIXED** — `_safe_name`, verified |
| Medium | Rate limiting configured (`rate_limit_per_minute=120`) but **not enforced** (no middleware) | OPEN — add slowapi/Redis limiter |
| Medium | Sandboxed Python-exec reachable by any authenticated user via `/functions/call` | OPEN — gate `python` behind instructor+ or remove from API |
| Medium | `pickle.load` for the BM25 index | OPEN — trusted source today; prefer a safe format |
| Medium | `DIGILER_SECRET_KEY` defaults to `change-me…` | OPEN — must set a strong secret in prod |
| Low | `.gitignore` minimal; `student.db`/`catalog.db` tracked | OPEN — expand ignore + untrack |
| OK | Auth (JWT access+refresh, bcrypt, RBAC) verified · SQLi low (ORM + parameterised) · CSRF low (JWT header, not cookies) · CORS specific origin (not wildcard) · XSS low (React escapes; ReactMarkdown no raw HTML) | — |

## Phase 6 — Code Quality

- **~21 unused imports across ~23,600 LOC** (excellent hygiene); **fixed** 4 backend imports +
  1 dead variable (upload). Remaining 15 are benign (mostly benchmark files in the frozen ala
  package) — documented, not churned.
- No dead logic. Candidate duplication: `bm25/tokenizer.py` vs `chunking/tokenizer.py` (review).
- 5 TODO/FIXME total.

## Phase 8 — Deployment Checklist

**Development:** `pip install -e . && pip install -r backend/requirements.txt` · `ollama pull qwen3`
· backend `uvicorn app.main:app` (single worker) · `cd frontend && npm i && npm run dev`.

**Docker / Production:**
- [ ] `docker compose up` (postgres/redis/qdrant/ollama/backend/frontend/nginx)
- [ ] **Purge + rotate the committed OAuth secret**; expand `.gitignore`; untrack `*.db`
- [ ] Set `DIGILER_SECRET_KEY` (long random), `DIGILER_DATABASE_URL` (Postgres), `DIGILER_CORS_ORIGINS`
- [ ] `ollama pull qwen3` on the ollama volume before serving
- [ ] Qdrant **server mode** (`retrieval.vector_store.location=http://qdrant:6333`) for concurrency,
      **or** run backend with a single uvicorn worker
- [ ] Alembic migrations for the web DB (`alembic upgrade head`)
- [ ] nginx (provided): `proxy_read_timeout 300s`, `proxy_buffering off` (SSE-safe) — keep
- [ ] Enforce rate limiting; gate/remove the `python` function
- [ ] **Backups:** Postgres dumps + the `data/` artifacts (catalog, qdrant, graph, bm25, student)
- [ ] **Logging:** ship uvicorn/app logs (request-id already emitted) to a collector
- [ ] **Monitoring:** add health/readiness probes (`/api/health`, `/api/ready`) + metrics (none yet)

---

## FINAL REPORT

**1. Overall project score: 84 / 100** — feature-complete, 240 tests, honest limitations,
clean architecture; docked for LLM latency, ops gaps, and security debt.

**2. Production-readiness score: 70 / 100** — solid core, but blocked by a committed secret,
no rate limiting, single-process vector store, and no monitoring.

**3. Remaining risks:** (a) committed OAuth secret [CRITICAL]; (b) no rate limiting; (c) Qdrant
local single-process (a 2nd opener 500s every AI endpoint); (d) ~20 s LLM latency (UX);
(e) Python-exec exposed to authenticated users; (f) no monitoring/observability.

**4. Known limitations:** local LLM required for fluent answers (extractive otherwise); cold
start 10 s / RSS 1.5 GB; `/research` still synchronous (~40–80 s); Wikipedia-only web breadth
without an API key; single-node design.

**5. Recommended future improvements:** stream `/research`; enforce Redis rate-limiting + caching;
Qdrant server mode; Prometheus/Grafana; disable Qwen3 "thinking" or offer qwen2.5 for snappier
first-token; quiz types (MCQ/TF); the UI/UX product redesign.

**6. Files modified (this audit):** `backend/app/api/routers/upload.py` (path-traversal fix +
dead var), `admin.py`/`instructor.py`/`core/config.py` (unused imports). Prior phases:
`chat_service.py`, `search.py`/`citations.py`/`knowledge.py` (retrieval-only + streaming),
`agents/tools.py`, `llm/ollama.py`, `rag/llm.py`, `research/search.py`+`models.py`, frontend
`lib/stream.ts`+`knowledge/page.tsx`+`chat-view.tsx`, config/nginx/compose.

**7. Test results:** **ala 232 + backend 8 = 240 passed** (with Ollama active); frontend
`tsc` + `next build` clean (13 routes).

**8. Performance summary:** retrieval ~73 ms; generation ~20 s (LLM-bound); SSE headers 0.23 s;
warm endpoints 1–130 ms; cold start 10.6 s; RSS 1.5 GB.

**9. Security summary:** 1 critical (committed secret, open), 1 high (traversal, fixed),
4 medium (rate-limit, python-exec, pickle, default key — open), auth/RBAC/CORS/SQLi/CSRF sound.

**10. Go / No-Go:**
- ✅ **GO for a controlled demo / internal pilot** — behind nginx, single worker, model pulled,
  a real secret key set. All features work end-to-end.
- ⛔ **NO-GO for public multi-user production** until the CRITICAL secret is purged + rotated,
  a strong `DIGILER_SECRET_KEY` is set, rate limiting is enforced, Qdrant runs in server mode,
  and basic monitoring exists. These are finite, well-understood, and none require redesign.
