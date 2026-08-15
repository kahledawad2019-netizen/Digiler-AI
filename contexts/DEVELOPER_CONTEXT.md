# ALA — Developer Context

> **Read this first.** It lets any AI coding assistant (Claude, Cursor, …) or new
> engineer understand the project without re-reading the full proposal. Pair it
> with the live machine-readable state in
> [`contexts/project_context.yaml`](project_context.yaml) (run `ala context refresh`).

---

## 1. Vision
A **local-first, RAG-based AI learning platform** for Digilians educational
materials. A student asks in English or Arabic and gets a verified, cited answer
grounded in *their* course materials — with quizzes, flashcards, a concept map,
spaced-repetition practice, and (later) video and web knowledge. The organising
idea is the **Resource Fabric**: one ingestion spine, many source adapters, one
evidence model — so every new capability (video, web, graph) is additive, not a
rewrite.

## 2. Architecture summary (baseline: V3, frozen)
Source of truth: [`ALA_Architecture_v3.md`](../ALA_Architecture_v3.md). Key points:
- **Resource Fabric** — every source (PDF/PPTX/DOCX/MD/HTML/YouTube/web) becomes
  the same `LearningResource` (metadata + unified `ContentBlock`s).
- **Retrieval** — hybrid: dense (multilingual-e5/bge-m3) + BM25 + concept-graph,
  fused with RRF; parent–child chunking; sufficiency gate → web fallback.
- **Concept Graph** — scoped curriculum graph (SQLite + NetworkX, *not* Neo4j);
  three consumers: retrieval, Coach/RL, Study-Map UI.
- **Agents (5)** — Learning, Summarization, Quiz, Flashcard, Coach — + Router
  (stage) + Verifier (stage). Web search & video ingestion are **tools**, not agents.
- **Personalization** — Elo per-concept student model; RL = quiz bandit + review
  scheduler (curriculum-RL rejected).
- **Verifier** — per-claim entailment against cited evidence; refuses rather than
  guesses; surfaces KB-vs-web conflicts.

## 3. Tech stack & dependencies
- **Language:** Python 3.11+ (invoke via the `py -3` launcher on this machine;
  there is no bare `python` on PATH). Virtualenv at `.venv`.
- **Current deps (minimal, deliberate):** `pydantic>=2` (typed self-validating
  models), `pyyaml` (config/taxonomy). Standard library: `sqlite3` (catalog),
  `hashlib` (change detection), `argparse` (CLI).
- **Declared-but-not-yet-installed:** ingestion loaders (`pypdf`, `python-pptx`,
  `python-docx`, `beautifulsoup4`, `nbformat`); later: ChromaDB, sentence
  embeddings, faster-whisper, NetworkX, LangGraph, Streamlit.
- **Never add a dependency without justification.** Prefer stdlib.

## 4. Folder structure
```
config/           platform.yaml + taxonomy/ (tracks, languages, concept seeds)
contexts/         context.declared.yaml, project_context.yaml (generated), this file
knowledge_base/   NEW managed corpus: raw/ (immutable + sidecars) + derived/ (regenerable)
KNOWLEDGE BASE/    ORIGINAL materials — READ-ONLY, do not touch (migration is approval-gated)
src/ala/
  core/           enums, ids, hashing, clock, exceptions   (no internal deps)
  config/         settings loader
  metadata/       ResourceMetadata schema (v2.0.0 FROZEN), sidecar, validation
  catalog/        SQLite: schema.sql, database, repository (KnowledgeCatalog)
  registry/       ResourceRegistry, change_detection
  fabric/         LearningResource, ContentBlock, Anchor, SourceAdapter
  context/        ProjectContext models + service
  cli.py          `ala` command
tests/            pytest suite (run: py -3 -m pytest)
docs/             per-milestone documentation
data/catalog/     generated SQLite DB (gitignored)
```

## 5. Design principles & engineering rules
- **Clean Architecture + SOLID.** `core` depends on nothing; higher layers depend
  inward. Validation rules and source adapters are Open/Closed (add a class,
  don't edit the runner).
- **Config over hardcode.** Paths, versions, taxonomy, component statuses live in
  YAML, not literals.
- **Raw is immutable; derived is regenerable.** Loaders/embedders write only to
  `knowledge_base/derived/`; originals are never mutated.
- **Stable IDs, not paths.** Everything references `resource_id`
  (`<track>.<course>.<module>.<slug>`); reorganising files never breaks refs.
- **Reserve fields, don't migrate.** The metadata schema already carries the
  fields future phases fill (`retrieval.*`, `video`, `web`, `provenance.history`).
- **Compose, don't duplicate.** `LearningResource` contains `ResourceMetadata`.
- **Bilingual from day one.** `language` is first-class on resource/block; concept
  nodes are multilingual; Arabic content will be added.
- **Every module ships docs + tests.** No exceptions.

## 6. Naming conventions
- `resource_id`: `technical.dmv.w03.constraints-relationships` (lowercase a-z0-9-).
- On disk each resource is `raw/<track>/<course>/<module>/<slug>/source.<ext>`
  with a `source.<ext>.meta.json` sidecar. Human titles live in metadata, not
  filenames (so Arabic titles are a non-issue).
- Python: `snake_case` functions, `PascalCase` classes, `_StrEnum`-backed enums.

## 7. Current progress
| Milestone | Scope | Status |
|---|---|---|
| **M1** | KB infrastructure: metadata, catalog, registry, versioning, change detection, validation (Tasks 1–4) | ✅ done |
| **M1.5** | Resource Fabric (`LearningResource`) + schema v2.0.0 **frozen** | ✅ done |
| **M2** | Project Context + Developer Context (Tasks 5–6) | ✅ this milestone |
| **M3** | Ingestion Pipeline (Task 7): loaders → `LearningResource`; no embeddings | ⏭ next |

## 8. Remaining milestones (indicative, per V3 phases)
Ingestion loaders → Parent-Child chunking → Hybrid retrieval core + eval harness
→ Agents + Router + Verifier → Concept Graph → Video adapter → Student Model + RL
→ Web fallback → full evaluation campaign. A pre-agreed **cut list** (V3 §13.2)
governs what gets de-scoped if time runs short.

## 9. Important constraints
- **Local-first, zero-infra:** in-process only (SQLite, ChromaDB, NetworkX). No
  servers (Neo4j rejected for this reason).
- **Privacy:** local by default; web/LLM calls only by explicit consent (V3 §5.4).
- **Data rights:** Digilians materials are personal-study, no redistribution.
- **Don't touch `KNOWLEDGE BASE/`** — the original corpus is read-only until a
  migration is approved.

## 10. Working agreement (how we build)
Incremental milestones; after each, explain what/why/what-changed/how-to-test and
**wait for approval** before the next. Challenge weak design decisions; don't
over-engineer. Commit/push only when explicitly asked.

## 11. How to run
```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q          # test suite
.\.venv\Scripts\ala.exe context show             # live self-description
```
