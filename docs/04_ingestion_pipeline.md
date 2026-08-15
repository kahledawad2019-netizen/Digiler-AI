# Milestone 3 — Ingestion Pipeline

**Status:** implemented & tested (**76 passing tests**, 54 modules). Architecture
baseline: **V3**. Produces high-quality structured data only — **no chunking,
embeddings, vectors, BM25, graph, agents, or RL** (those are later milestones).

---

## 1. Architecture

The pipeline is the platform's **data-processing backbone**: every resource that
enters the system passes through it and comes out as a unified, structured
`LearningResource` + a persisted `ResourcePackage`.

```
                 ┌── Stage 1: Resource Discovery (find + classify files) ──┐
                 ▼                                                          │
  IngestionJob (path + classification)                                     │
     │                                                                     │
     ▼   registry.build_metadata()  ── metadata seed (not yet persisted)   │
  LearningResource (empty)                                                 │
     │                                                                     │
     ▼   ── ordered stages, each: resource in → resource out ──            │
  [2 Validation] → [3 Loader Selection] → [4 Extraction] → [5 Normalize]   │
  → [6 Language] → [7 Structural] → [8 Academic] → [9 Enrich] → [10 Package]│
     │                                                                     │
     ▼   registry.commit()  ── Registry Update → Knowledge Catalog Update ─┘
  IngestionResult (status, resource, package, structured outcomes)
```

**Key design decisions**

- **Stages are pure and replaceable.** Each implements
  `process(resource, ctx) -> resource` and communicates only through the
  resource and a shared `PipelineContext` — never with each other. Reorder or
  swap any stage without touching the rest (Liskov / Open-Closed).
- **Cross-cutting concerns live once, in the orchestrator:** timing, per-stage
  retry, structured-error capture, and processing-history. Stages stay focused.
- **Dependency injection throughout.** Loaders, the language detector, the
  academic detector, and the derived-root are injected — so a real ML language
  model or a new loader is a constructor argument, not a rewrite. The PDF loader
  even injects its page-extractor, so it is unit-tested without a real PDF.
- **Errors never crash the batch.** A critical-stage failure fails *that*
  resource (`FAILED`); a non-critical failure yields `PARTIAL`; one bad file
  never stops directory ingestion. Every stage emits a structured `StageOutcome`.
- **Structure is preserved, never flattened.** Loaders emit typed `ContentBlock`s
  (heading / paragraph / list / table / code / caption …) with citation anchors;
  normalization is type-aware (code/tables are never reflowed).

---

## 2. Pipeline stages

| # | Stage | Class | Critical? | What it does |
|---|---|---|---|---|
| 1 | Resource Discovery | `ResourceDiscovery` | — | Finds files; infers track/course/module/doc_type from the managed layout. |
| 2 | File Validation | `FileValidationStage` | ✅ | Rejects missing / oversized / unsupported files; warns on empty. |
| 3 | Loader Selection | `LoaderSelectionStage` | ✅ | `LoaderRegistry` picks a loader by extension. |
| 4 | Content Extraction | `ContentExtractionStage` | ✅ (retryable) | Runs the loader → structured blocks. Warns (not fails) on 0 blocks → *"OCR may be needed."* |
| 5 | Cleaning & Normalization | `CleaningNormalizationStage` | — | Unicode NFC, smart-quote/whitespace/control-char cleanup, broken-line reflow, repeated header/footer removal — **type-aware**. |
| 6 | Language Detection | `LanguageDetectionStage` | — | Script-based detector → resource + per-block language **with confidence**. |
| 7 | Structural Parsing | `StructuralParsingStage` | — | Promotes heading-like paragraphs (rescues structure from PDF/text). |
| 8 | Academic Structure | `AcademicStructureStage` | — | Detects week/lecture/section/topic/subtopic + examples/exercises/assignments/labs/references; enriches metadata. |
| 9 | Metadata Enrichment | `MetadataEnrichmentStage` | — | Keywords, estimated study time, content statistics. |
| 10 | Resource Packaging | `ResourcePackagingStage` | ✅ | Builds the `ResourcePackage` and persists it (+ the `LearningResource`) to `derived/`. Sets status → `extracted`. |
| — | Registry / Catalog Update | `registry.commit()` | — | Sidecar + catalog row + event; fires the Project-Context refresh hook. |

**Loaders** (each implements the `SourceAdapter` contract; heavy deps imported
lazily): `TextLoader` (.txt), `MarkdownLoader` (.md), `HtmlLoader` (.html, bs4),
`PdfLoader` (.pdf, pypdf), `PptxLoader` (.pptx, python-pptx), `DocxLoader`
(.docx, python-docx), `NotebookLoader` (.ipynb, nbformat). Future YouTube / web /
image-OCR adapters plug into the same registry.

**The ResourcePackage** (Stage-10 output, saved to
`knowledge_base/derived/<resource_id>/package.json`) contains exactly what the
milestone requires: metadata · structured content blocks · clean text · language
(+confidence) · academic structure · processing history · validation results ·
stats. No embeddings/chunks/vectors/graph.

---

## 3. Directory structure

```
src/ala/ingestion/
├── __init__.py            public surface
├── errors.py              IngestionError family + StageOutcome
├── config.py              PipelineConfig (parsed from platform.yaml `ingestion:`)
├── context.py             ResourceClassification, IngestionJob, PipelineContext
├── result.py              IngestionStatus, IngestionResult, ResourcePackage
├── discovery.py           Stage 1 — ResourceDiscovery
├── pipeline.py            IngestionPipeline (orchestrator)
├── loaders/
│   ├── registry.py        LoaderRegistry + default_loaders()
│   ├── base.py            BaseLoader + BlockSpec (template method)
│   ├── markdown_parse.py  shared structure-preserving Markdown parser
│   ├── text_loader.py  markdown_loader.py  html_loader.py
│   ├── pdf_loader.py  pptx_loader.py  docx_loader.py  notebook_loader.py
├── text/
│   ├── normalize.py       normalization primitives (pure functions)
│   ├── language.py        LanguageDetector protocol + ScriptLanguageDetector
│   └── academic.py        AcademicStructureDetector
└── stages/
    ├── base.py            PipelineStage protocol + BaseStage
    ├── preprocessing.py   Stages 2-4
    ├── processing.py      Stages 5-7
    └── enrichment.py      Stages 8-10

config/platform.yaml       new `ingestion:` block (limits, normalization, cues)
tests/  test_loaders.py test_ingestion_text.py test_stages.py test_pipeline.py
```

---

## 4. How to test it

```powershell
.\.venv\Scripts\python.exe -m pytest -q          # 76 passed
```

Coverage: **unit** (every loader with a real generated file of its type; the PDF
loader via an injected page-extractor; normalization / language / academic
utilities; each stage in isolation) and **integration** (full pipeline on
Markdown / DOCX / PPTX; graceful failure on unsupported files; directory
ingestion isolating a broken file from a good one).

**Try it on real files** (CLI):
```powershell
# single file
.\.venv\Scripts\ala.exe ingest <path> --track technical --course dmv --module w01 `
      --title "Week 1" --doc-type lesson_page
# whole managed tree (discovery infers classification from raw/<track>/<course>/<module>/)
.\.venv\Scripts\ala.exe ingest-dir
```

**Verified on the real corpus** (copied into the managed tree, originals in
`KNOWLEDGE BASE/` untouched): a clean lesson PDF produced 9 page-anchored blocks,
`en` @ confidence 1.0, week 1 detected; a scanned PDF produced 0 blocks with an
automatic *"OCR may be needed"* warning — both processed without error, exactly
the behaviour the KB audit predicted.

---

## 5. What is deliberately NOT here
Chunking, parent–child, embeddings, vector DB, BM25, hybrid retrieval, Graph RAG,
agents, RL. The output is high-quality structured data those milestones consume.
The schema already reserves their fields (`retrieval.*`), so they add, not migrate.
