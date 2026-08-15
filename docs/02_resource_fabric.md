# Milestone 1.5 — Resource Fabric + Metadata Schema Freeze (v2.0.0)

**Status:** implemented & tested (**44 passing tests**). Schema proposed for
**freeze at `2.0.0`**. Architecture baseline: **V3**.

This milestone does two things:
1. Establishes the **unified internal representation** (`LearningResource`) that
   every source type — PDF, PPTX, DOCX, MD, HTML, YouTube, web — becomes, *before*
   we build any loader.
2. Extends and **freezes** the metadata schema after a critical review of the
   proposed additions.

---

## Part A — The Resource Fabric

### What it is
One object, `LearningResource`, that the whole platform speaks. A loader turns a
raw source into it; chunkers, embedders, the graph builder, RL, and citations
all read it. **They never touch a file format again.**

```
raw source ──(SourceAdapter)──▶ LearningResource ─┬─▶ Parent-Child chunking
                                                  ├─▶ Hybrid RAG (dense + BM25)
   LearningResource =                             ├─▶ Graph RAG (concepts + section_path)
     metadata : ResourceMetadata   (the descriptor)├─▶ RL / Student Model (difficulty, items)
     blocks   : [ContentBlock]      (unified content)─▶ Citations (typed Anchor)
     warnings : [str]
```

### Key design decision: compose, don't duplicate
`LearningResource` **contains** a `ResourceMetadata` — it does not re-declare its
fields. The descriptor is persisted in the catalog (Milestone 1); the content
(`blocks`) is persisted under `knowledge_base/derived/<resource_id>/` and is
fully regenerable. This is what keeps "one ontology everywhere."

### `ContentBlock` — the atomic unit
A block is a paragraph / slide / notebook cell / transcript window with:
- `type` (`BlockType`) — source-agnostic (`heading`, `paragraph`, `slide`, `table`, `code`, `image_caption`, `transcript_segment`, …)
- `text`, `order`, stable `block_id`
- `language` **per block** (supports code-switched Arabic/English material)
- `anchor` (`Anchor`) — typed citation pointer: `p.14` / `slide 7` / `12:34` / `cell 3`
- `section_path` — heading breadcrumb → seeds Parent-Child grouping and the graph
- `meta` — per-block `ocr_confidence` / `asr_source` → feeds Verifier caveats

### `SourceAdapter` — the loader contract (the Task-7 seam)
A `Protocol`: `can_handle(path)` + `load(path, metadata) -> LearningResource`.
Task 7 adds PDF/PPTX/DOCX/HTML/notebook/YouTube/web adapters; nothing else
changes (Open/Closed). **`PlainTextAdapter`** is the working reference
implementation for `.txt`/`.md` — it proves the fabric end-to-end without any
heavy dependency (it splits paragraphs, tracks headings, records char anchors,
and appends a processing-history step). It is *not* the ingestion pipeline.

### Files
```
src/ala/fabric/
├── content.py            # BlockType, Anchor, ContentBlock
├── learning_resource.py  # LearningResource (+ save/load to derived/)
└── adapters.py           # SourceAdapter protocol + PlainTextAdapter reference
```

---

## Part B — Metadata schema v2.0.0 (critical review outcome)

Proposed additions were reviewed for over-engineering before freezing. Outcome:

| Category | Decision |
|---|---|
| **Academic** (`academic` sub-model): course_code, instructor, semester, estimated_study_time_min, lab_required, exam_weight | ✅ added |
| `difficulty_score` (numeric, for RL) | ✅ added into `pedagogy` beside the `difficulty` band |
| `track` | ❌ already top-level (duplicate) |
| `learning_outcomes` | ❌ reuse `pedagogy.learning_objectives` (duplicate) |
| `program`, `prerequisite_courses` | ⚠️ redirected to **taxonomy** (course-level facts; would drift if per-resource) |
| **Relationships** (related/depends_on/extends/recommended_*/similar) | ✅ collapsed into **one typed edge list** `relationships: [{type, target, source: manual\|derived, confidence}]` — mirrors the Concept Graph edge model; computed links carry `source=derived` and stay recomputable |
| **Video** (`video` sub-model): video_id, channel, playlist, duration_sec, transcript_language, transcript_version, asr_source | ✅ added — **nullable**, present only for `doc_type=video` |
| **Web** (`web` sub-model): domain, crawl_date, last_verified, source_tier | ✅ added — **nullable**; `url`/`license` reuse `source.*` (not duplicated) |
| **Student personalization** (bookmarked, favorite, mastered, review_required) | ❌ **rejected from resource schema** — per-student mutable state; belongs in the **Student Model** (`student_resource_state` table, keyed by `(student_id, resource_id)`). `mastered` is per-concept-per-student and computed by Elo — a resource boolean would conflict with the mastery table. |
| **Processing provenance history** (step, timestamp, tool, version, duration, status) | ✅ added — `provenance.history: [ProcessingStep]`, appended via `metadata.add_processing_step(...)` |

**Why the personalization rejection matters:** the resource descriptor stays
*about the resource* — stable, shareable, single-owner. Per-student flags are a
different entity (a student↔resource edge) and get their own store when we build
the Student Model. Nothing is lost; it's homed correctly.

### Promoted catalog columns (new, filterable)
`difficulty_score`, `course_code`, `instructor`, `lab_required`, `has_video`,
`has_web` — everything else remains in `metadata_json`. Catalog schema →
`1.1.0`.

### Migration impact: none
No real resources are registered yet (the M1 demo was cleaned up), so the
`1.0.0 → 2.0.0` change is free. New nullable fields default cleanly; the catalog
DB is regenerable via `ala init`.

---

## How to test
```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 44 passed
```
New suites: `tests/test_fabric.py` (LearningResource, anchors, adapter,
derived save/load) and `tests/test_metadata_v2.py` (academic, difficulty_score,
typed relationships, nullable video/web, processing history, round-trip).

## What's frozen after this
`ResourceMetadata` v2.0.0 and `LearningResource` are the stable contracts.
Later phases **fill** reserved fields (`retrieval.*`, `provenance.history`,
`video`, `web`) rather than reshape them.
