# Frontend / UX Audit — verification & fixes

**Hard limitation stated up front:** this environment has **no browser automation and no
screenshot capability**. I cannot click buttons or capture rendered pixels. So I verified the
way the browser actually behaves under the hood — real HTTP + SSE against a live uvicorn
server, plus TypeScript type-checking and production build — and I fixed real defects. Any
item that can *only* be confirmed by a human looking at the screen is marked
**⚠ needs your browser confirmation**, not claimed as done.

Servers observed live during this audit: frontend :3000, backend :8000, Ollama :11434.

## Fixed this session (with real verification)

### 1. Logo / branding — FIXED
- **Root cause:** `public/` contained only `README.md` — **no `logo.png`** — so `/logo.png`
  and the favicon returned **404** (confirmed via curl on :3000).
- **Fix:** shipped a self-contained **inline SVG brand mark** (`components/logo.tsx` → `LogoMark`,
  grad-cap + book + concept-nodes, blue→purple) so it renders with **no external-file
  dependency (can never 404)**, plus `public/logo.svg` wired as the favicon (`app/layout.tsx`).
- **Backend:** none. **Frontend:** `components/logo.tsx`, `app/layout.tsx`, `public/logo.svg`.
- **Verification:** `next build` clean; inline SVG needs no fetch. **Files:** logo.tsx, layout.tsx, logo.svg.
- **Limitation:** it's a brand-appropriate SVG, not your exact raster art — drop your `logo.png`
  in `public/` and swap `<LogoMark/>` for `<img src="/logo.png">` to use the original.

### 2. Quiz — now INTERACTIVE (was plain text) — FIXED
- **Root cause:** the endpoint returned one extractive text question; the UI just printed it.
- **Fix (backend):** new `POST /api/quiz` (`services/quiz_service.py`, `routers/quiz.py`) —
  Qwen3 generates **4 structured questions (multiple-choice / true-false / short-answer)** with
  options, correct answer, and explanation, grounded in retrieved evidence; robust JSON parsing;
  **extractive fallback** if the LLM is down; `/no_think` to keep generation ~30 s (was 152 s).
- **Fix (frontend):** `components/quiz/quiz-runner.tsx` — radio options, **Submit**, immediate
  **correct/incorrect feedback**, correct answer highlighted, **explanation**, **Next**, running
  **score + progress bar**, and **New quiz** (retry). Wired into the Knowledge Base resource panel.
- **Backend endpoint:** `POST /api/quiz`. **Frontend component:** `QuizRunner` in `knowledge/page.tsx`.
- **Verification (real HTTP + Qwen3):** `HTTP 200`, `source=llm`, returned **2 MCQ + 1 TF + 1 short**,
  each with options/answer/explanation, in ~30 s. JSON parser unit-tested against messy LLM output.
- **Files:** `quiz_service.py`, `quiz.py`, `api/router.py`, `quiz-runner.tsx`, `knowledge/page.tsx`,
  `lib/client.ts`, `types/index.ts`.
- **⚠ needs your browser confirmation:** the click-through (radio → submit → feedback → next → score).
  The data and component are verified; the on-screen interaction I cannot click.
- **Limitation:** ~30 s to generate (Qwen3). A loading card is shown meanwhile.

### 3. Chat & Summarize streaming — VERIFIED + faster first token
- **Root cause of "no response / empty box":** streaming works, but Qwen3's *thinking* delayed
  the first token ~30 s, so the box looked empty. (Also, if your servers run pre-fix code, the old
  sync path reset.)
- **Fix:** `/no_think` on the streaming prompt (`chat_service.stream_answer`) to shorten prefill;
  the UI already shows a typing indicator immediately.
- **Verification (real uvicorn + httpx, not TestClient which buffers):** headers flush at **0.23 s**;
  chat streamed **147 token-frames incrementally** — first token +18.6 s, then progressive over ~4 s;
  summarize streamed **1,696 chars**. Content is delivered, connection stays alive, no reset.
- **Backend:** `POST /api/chat/stream`, `POST /api/knowledge/resource/{id}/summarize/stream`.
  **Frontend:** `chat-view.tsx`, `ResourcePanel` (`streamSummary` in `lib/stream.ts`).
- **Limitation:** ~18 s to first token is Qwen3 prefill/thinking (model latency). Use **qwen2.5**
  for a snappier first token. The pipeline itself is not the bottleneck (retrieval is ~73 ms).

## Verified at the API/contract level (backend proven; ⚠ on-screen render needs your confirmation)

| Feature | Backend endpoint | Frontend component | Status |
|---------|------------------|--------------------|--------|
| Auth (register/login/logout/refresh/protected) | `/api/auth/*` | `login/page.tsx`, `store/auth.ts`, `lib/api.ts` | Backend + refresh interceptor verified ✓ |
| Knowledge Base (courses/weeks/resources/summarize/quiz/citations/related/upload) | `/api/knowledge/*`, `/api/upload` | `knowledge/page.tsx` | Backend verified (7 courses, tree, related, upload guards) ✓ |
| Planner (page/route/generate/regenerate) | `/api/planner` | `planner/page.tsx` (+ link on Profile) | Backend verified; route builds ✓ |
| Search (knowledge) | `/api/search` | `chat`/`knowledge` | Backend verified (100 ms, evidence) ✓ |
| Research / Web search | `/api/research` | chat approval flow | Backend verified (Wikipedia, used_web=true) ✓ |
| Dashboard + recommendations | `/api/dashboard` | `profile/page.tsx` | Backend verified (recs populate) ✓ |
| Personalization (student model / RL) | `/api/student`, RL in agents | profile / planner | Backend verified ✓ |
| Agents | `/api/agents/*` | not surfaced in UI | Backend verified; **not visible in UI** (backend-internal) ⚠ |
| Settings (preferences/LLM/logout) | `/api/student/preferences`, `/api/llm` | `settings/page.tsx` | Backend verified; theme/language are UI-only ⚠ |

## Honest gaps I did NOT fully close this session
- **Agents are not surfaced in the UI** — they run server-side (chat/quiz/planner use them), but
  there is no dedicated "Agents" screen. If you want them visible, that's a new UI surface to build.
- **Settings theme toggle / dark mode / password change** — the Settings page has preferences + LLM
  status, but **no dark-mode toggle and no change-password flow** yet.
- **Responsive (tablet/mobose) and the broader visual polish (#16)** — the layout uses responsive
  utilities and builds, but I **cannot verify responsive breakpoints without a browser**; a
  design pass is still outstanding.
- **The full click-through of every screen (#17)** cannot be executed from here — it needs a human
  in the browser after restarting both servers on the current code.

## What you must do to see all of this
Your `:8000` backend and `:3000` frontend are running **older code**. **Restart the backend**
(`uvicorn app.main:app`, single worker) and **rebuild/restart the frontend** (`npm run build && npm start`,
or restart `npm run dev`). Then: the logo appears, quiz is interactive, chat/summarize stream.
