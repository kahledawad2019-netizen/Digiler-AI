# LLM Endpoint Architecture Audit & Remediation

Goal: eliminate the class of bug where a synchronous endpoint runs a long LLM
generation that exceeds the frontend proxy timeout and resets the socket. Every number
below is from real execution (in-process ASGI, real corpus, **Ollama Qwen3 active**).

## Root pattern

Several endpoints called `GraphRAGService.answer_with_context()` — the full pipeline
`retrieve → build context → **LLM generate**` — but only used the retrieved evidence
package and **discarded the generated answer**. With no LLM this was instant; with Qwen3
it became a 20–40 s wasted generation → proxy reset.

## Endpoints audited & classification

| Endpoint | Needs generation? | Decision | Action |
|----------|-------------------|----------|--------|
| `GET /search` | No (uses evidence only) | **Retrieval-only** | `answer_with_context` → `retrieve_package` |
| `POST /citations` | No (citation index from package) | **Retrieval-only** | → `retrieve_package` |
| `GET /knowledge/resource/{id}/citations` | No (citations only) | **Retrieval-only** | `build_answer` → `citations_only` |
| `POST /knowledge/resource/{id}/quiz` | No (extractive quiz) | **Retrieval-only** | (fixed prior) `evidence()` → merger |
| `POST /knowledge/resource/{id}/summarize` | **Yes** (writes a summary) | **Stream (SSE)** | added `…/summarize/stream` |
| `POST /chat/stream` | Yes | **Stream (SSE)** | already correct ✓ |
| `POST /chat` | Yes | Sync (API only; UI uses stream) | kept; prod-proxy covered |
| `POST /research` | Yes (researched answer) | Sync (user-gated) | kept; recommend stream next |
| `POST /agents/ask`, `/agents/session` | Yes (tutor) | Sync (backend-internal, not UI) | kept |
| planner / dashboard / student / graph / tree / related / auth / admin / instructor | No | Already retrieval/DB-only | none |

## Before → after (warm, Qwen3 active)

| Endpoint | Before | After | Speedup |
|----------|-------:|------:|--------:|
| `GET /search` | 23,645 ms | **113 ms** | 209× |
| `GET /resource/{id}/citations` | 37,055 ms | **254 ms** | 146× |
| `POST /citations` | 11,446 ms | **155 ms** | 74× |
| `POST /resource/{id}/quiz` | 53,000 ms | **60 ms** | ~880× |
| `POST /resource/{id}/summarize` | 23,984 ms (sync, reset-prone) | **streaming**, 200 headers immediate, reset-proof | — |

Retrieval-only endpoints are now pure retrieval (~60–260 ms). The generative ones stream.

## Architectural changes

1. **`chat_service.retrieve_package()` / `citations_only()`** — retrieval-only helpers over
   `pipeline.merger.merge()` (no generator). Used by search + both citations endpoints.
2. **`POST /knowledge/resource/{id}/summarize/stream`** — SSE summary, reusing the chat
   streaming pipeline (`stream_answer` generalized with `filters`). Frontend `ResourcePanel`
   now streams the summary (shared `pumpSSE` in `lib/stream.ts`, new `streamSummary`).
3. **`stream_answer(..., filters=…)`** — retrieval filter passthrough so any resource-scoped
   stream works.

## Timeout & socket-reset handling

- **Backend never resets:** `RequestContextMiddleware` catches every unhandled exception and
  returns a structured JSON 500 (`{detail, request_id}`); the quiz endpoint returns 422/503
  JSON. FastAPI always emits a response — the earlier "reset" was purely the proxy giving up.
- **Streaming endpoints are reset-proof:** 200 headers flush immediately, sse-starlette sends
  periodic pings during generation, so the connection stays alive regardless of LLM latency.
- **LLM timeout is config-driven:** `platform.yaml → llm.timeout` (120 s); on timeout/any
  LLM error `LLMBackedGenerator` degrades to the grounded extractive generator (200, never 500).

## Proxy / server timeout audit

| Layer | Setting | Verdict |
|-------|---------|---------|
| Prod reverse proxy (nginx) | `/api/`: `proxy_read_timeout 300s`, `proxy_buffering off`, `proxy_cache off` | ✓ SSE-safe, adequate for sync generation |
| Dev proxy (Next rewrites) | no explicit timeout; resets long sync requests (~>50 s) | mitigated: hot paths are now fast or streaming |
| Backend (uvicorn) | no request timeout (waits) | ✓ |
| Frontend (axios) | no timeout on client | ✓ (streaming bypasses it) |

## Verification

- Direct backend measurement of every affected endpoint (table above). ✓
- Streaming summarize verified over SSE (200, streams 1,816 chars, reset-proof). ✓
- Frontend `tsc --noEmit` clean + `next build` clean (13 routes). ✓
- Regression: **ala 232 + backend 8 = 240 pass** with Ollama active. ✓

## Remaining bottlenecks / recommendations

- **Generation latency is inherent:** streaming summary/chat first-token is ~30 s with Qwen3
  (its "thinking" phase delays visible content). It never resets, but for snappier UX either
  disable Qwen3 thinking (model options) or use a lighter model (qwen2.5). This is model
  tuning, not architecture.
- **`POST /research`** is still synchronous (two generations, ~40–80 s). It is user-gated
  (explicit Approve) and covered by nginx in prod; **recommend converting it to SSE** next,
  reusing the same streaming pattern.
- **`POST /chat` (non-streaming)** remains for programmatic/API use; the UI uses `/chat/stream`.
- **Production deployment:** always run behind the provided nginx (300 s, buffering off); run
  uvicorn with a **single worker** (Qdrant local mode) or switch Qdrant to server mode; pull
  the Ollama model before serving; keep `llm.timeout` aligned below the reverse-proxy timeout.
