# Digiler AI — Web Frontend

Chat-first web client for the Digiler AI Learning Platform. It is a **thin UI layer**
over the existing FastAPI backend (`../backend`): it renders capabilities that already
exist — Hybrid Retrieval / GraphRAG, citations & evidence, the student model, the study
planner, agents, and function calling — and adds no business logic of its own.

## Stack

- **Next.js 14** (App Router) · **TypeScript** · **TailwindCSS** · shadcn-style UI primitives
- **React Query** (server state) · **Zustand** (auth/session) · **Axios** (with token refresh)
- **SSE streaming** chat (fetch-based) · **Framer Motion** (minimal), **Recharts**
- Design: professional, minimal, academic — blue on white, no emojis

## Prerequisites

- Node.js 18.18+ (or 20+)
- The backend running and reachable (default `http://localhost:8000`)

## Setup

```bash
cd frontend
cp .env.local.example .env.local        # point NEXT_PUBLIC_API_URL at the backend
# place the Digiler logo at public/logo.png (see public/README.md)
npm install
npm run dev                             # http://localhost:3000
```

Production build:

```bash
npm run build
npm run start
```

## How it talks to the backend

`next.config.mjs` proxies `/api/*` to `NEXT_PUBLIC_API_URL`, so the browser always talks
same-origin and there are no CORS surprises in the browser. All calls go through
`src/lib/api.ts` (axios) — the request interceptor attaches the JWT access token and the
response interceptor transparently refreshes it on a 401 and retries once.

## Structure

```
src/
  app/
    page.tsx              # redirects to /chat (chat is the first screen)
    login/                # login + register
    (app)/                # authenticated shell (sidebar + guard)
      chat/               # ChatGPT-style streaming chat  (/chat, /chat/[id])
      knowledge/          # file-explorer KB: summarize / quiz / related (via retrieval)
      courses/            # course cards from the knowledge tree
      profile/            # profile + embedded dashboard (mastery, weak/strong, study time)
      planner/            # study planner over the existing planner service
      settings/           # learning preferences + LLM status
  components/
    sidebar.tsx           # New Chat · Knowledge Base · Courses · Settings · Recent · Profile
    chat/                 # message rendering + streaming chat view
    ui/                   # button, card, input, textarea, badge, avatar, skeleton
  lib/                    # api client, typed endpoint wrappers, SSE stream helper
  store/                  # Zustand auth store (persisted)
  types/                  # shared response types mirroring the backend schemas
```

## Notable behaviours

- **Chat is the landing screen** — every answer carries sources, page/slide/timestamp,
  confidence, retrieved documents, and an explanation path.
- **Web search is never automatic.** When confidence is low the answer shows
  *"This answer requires Web Search"* with **Approve / Cancel**; only on approval does the
  client call the research endpoint, which merges web results with the corpus.
- **Knowledge Base** never summarizes with the raw LLM — clicking a resource calls the
  retrieval-backed summarize endpoint. Uploads trigger the full backend ingestion pipeline.
- **Dashboard lives inside Profile**, not on the home screen.
