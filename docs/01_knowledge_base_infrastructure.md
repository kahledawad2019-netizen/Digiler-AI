# Milestone 1 — Knowledge Base Infrastructure

**Phase 1 · Tasks 1–4** · Status: **implemented & tested** (32 passing tests)
Architecture baseline: **V3** (frozen). This milestone builds the foundation the
whole platform stands on: identity, metadata, catalog, versioning, change
detection, and validation. **No embeddings, RAG, graph, or agents yet** — by
design.

---

## 1. What this is (plain English)

Before we can retrieve, embed, or reason over anything, the platform must know
**exactly what resources exist, what each one is, where it came from, whether it
changed, and what still needs processing.** That is this milestone.

Two synchronized stores hold the truth:

| Store | Form | Role |
|---|---|---|
| **Sidecar** | `*.meta.json` next to each raw file | human-readable, version-controllable, travels with the file |
| **Catalog** | one SQLite DB (`data/catalog/knowledge_catalog.db`) | fast lookup / filter / search / stats / event history |

The **Registry** is the one component that writes both, so they never drift.

### The data-flow in one picture

```
 raw file ──▶ ResourceRegistry.register()
                 │  compute sha256 + file facts
                 │  mint stable resource_id  (<track>.<course>.<module>.<slug>)
                 │  build ResourceMetadata   (validated by pydantic)
                 │  run ValidationPipeline    (taxonomy, files, state machine…)
                 ├─▶ write_sidecar()          → source.pdf.meta.json
                 └─▶ KnowledgeCatalog.upsert() → SQLite row + full JSON + event
                                                    │
 ChangeDetector.scan() ◀───────── compares disk sha256 vs catalog ──┘
     → NEW / MODIFIED / UNCHANGED / MISSING  → to_reprocess()
```

---

## 2. Directory structure

```
d:/Ai tools/
├── pyproject.toml                 # package, deps (pydantic, pyyaml), console script `ala`
├── config/
│   ├── platform.yaml              # central runtime config (paths, versions, policy)
│   └── taxonomy/
│       ├── tracks.yaml            # track → course → module ontology
│       ├── languages.yaml         # supported langs (en, ar), BM25 analyzer hints
│       └── concepts.seed.yaml     # multilingual Concept-Graph seed
├── knowledge_base/                # NEW managed tree (legacy "KNOWLEDGE BASE/" untouched)
│   ├── raw/                       #   immutable originals + sidecars
│   ├── derived/                   #   regenerable artifacts (gitignored)
│   ├── _incoming/  _quarantine/  _taxonomy/  _schemas/
│   └── (manifest.jsonl generated later)
├── data/catalog/                  # SQLite catalog (gitignored, regenerable)
├── src/ala/
│   ├── core/                      # enums, exceptions, clock, hashing, ids
│   ├── config/                    # settings loader (config-over-hardcode)
│   ├── metadata/                  # schema (Task 2), sidecar I/O, validation pipeline
│   ├── catalog/                   # schema.sql, database, repository (Task 3)
│   ├── registry/                  # registry (Task 4), change_detection
│   └── cli.py                     # `ala` command-line interface
├── tests/                         # 32 tests across 6 files
└── docs/01_knowledge_base_infrastructure.md   # this file
```

---

## 3. Classes & interfaces (the public surface)

### `ala.core`
- **`enums`** — controlled vocabularies: `DocType`, `Role`, `Language`,
  `ExtractionMethod`, `ChunkStrategy`, `ProcessingStatus`, `StageStatus`,
  `ValidationStatus`, `Persistence`, `RecordStatus`, `Difficulty`.
- **`ids`** — `slugify()`, `make_resource_id()`, `is_valid_resource_id()`.
- **`hashing`** — `sha256_file()`, `sha256_bytes()`, `sha256_text()`.
- **`clock`** — `Clock` protocol, `SystemClock`, `FixedClock` (deterministic tests).
- **`exceptions`** — `AlaError` root + `ConfigError`, `ValidationError`,
  `CatalogError`, `DuplicateResourceError`, `RegistryError`, …

### `ala.config`
- **`Settings`** — typed, fully-resolved config; `load_settings()`,
  `find_project_root()`. Absolute-path helpers (`catalog_db_path`, `raw_path`, …)
  and taxonomy accessors (`valid_track_ids()`, `valid_course_ids()`).

### `ala.metadata` — **Task 2**
- **`ResourceMetadata`** — the root pydantic model. Sub-models: `FileInfo`,
  `SourceInfo`, `ProvenanceInfo`, `PedagogyInfo`, `StatusInfo`, `LifecycleInfo`,
  `RetrievalInfo`. Methods: `to_json()`, `to_dict()`, `from_dict()`,
  `to_catalog_row()`, `touch()`.
- **`sidecar`** — `write_sidecar()`, `read_sidecar()`, `load_sidecar_for()`,
  `sidecar_path()`.
- **`validation`** — `ValidationPipeline`, `ValidationContext`,
  `ValidationResult`, and rule classes (`TaxonomyRule`, `FileExistsRule`,
  `HashIntegrityRule`, `StageConsistencyRule`, …). Add a rule → don't edit the
  runner (Open/Closed).

### `ala.catalog` — **Task 3**
- **`Database`** — thin SQLite layer (connection, pragmas, `schema.sql`).
- **`KnowledgeCatalog`** — repository:
  `upsert_resource()`, `get()`, `exists()`, `find_by_sha256()`,
  `find_by_content_hash()`, `filter()`, `search()`, `list_all()`, `count()`,
  `record_event()`, `get_events()`, `mark_superseded()`, `statistics()`.

### `ala.registry` — **Task 4**
- **`ResourceRegistry`** — `register()`, `set_status()`, `get()`,
  `from_settings()`. The only writer of both stores.
- **`ChangeDetector`** — `classify()`, `needs_reprocessing()`, `scan()`.
  **`ChangeReport`** — `summary()`, `to_reprocess()`.

---

## 4. How to test it

Prerequisites: Python 3.11+ (found here via the `py` launcher).

```powershell
# from d:/Ai tools
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# run the unit tests (32 tests)
.\.venv\Scripts\python.exe -m pytest -q
```

### Exercise it by hand with the CLI

```powershell
$ala = ".\.venv\Scripts\ala.exe"

& $ala init                                   # create catalog + KB folders
# register any file (writes a .meta.json beside it + a catalog row):
& $ala register <path-to-file> --track technical --course dmv --module w03 `
      --title "Constraints and Table Relationships" --doc-type lesson_page --week 3
& $ala scan --root knowledge_base/raw         # NEW/MODIFIED/UNCHANGED/MISSING report
& $ala validate --all --verify-hash           # run the validation pipeline
& $ala stats                                  # dashboard-ready statistics (JSON)
& $ala list                                   # tabular listing
& $ala show <resource_id>                     # full metadata JSON
& $ala events <resource_id>                   # provenance / change history
```

**What to look for:** a `*.meta.json` appears next to the file; `scan` flags the
resource for reprocessing while it is `pending`; editing the file then
`register --update` bumps the version and records a `content_changed` event;
`validate` reports `VALID`.

---

## 5. How each design requirement is met

| Requirement (Task) | Where |
|---|---|
| Resource Registry (T1, T4) | `registry/registry.py` — stable id, version, hash, status, relationships |
| Metadata System (T1, T2) | `metadata/schema.py` — all requested fields + RAG/Graph/RL/video/web reserved |
| Knowledge Catalog (T1, T3) | `catalog/` — SQLite, fast lookup/search/filter/stats, event log |
| Folder Structure (T1) | `knowledge_base/` raw+derived; legacy corpus untouched |
| Versioning (T1) | `LifecycleInfo` + `mark_superseded()` + version bump on update |
| Incremental Indexing (T1) | `ChangeDetector.scan().to_reprocess()` + per-stage `StageStatus` |
| Change Detection (T1) | `registry/change_detection.py` — sha256 authoritative |
| Validation Pipeline (T1) | `metadata/validation.py` — extensible rule set |
| JSON beside resource + global catalog (T2) | `sidecar.py` + `KnowledgeCatalog` (kept in sync by the Registry) |

## 6. Deliberately deferred (future phases, fields already reserved)

- Extraction/OCR/embedding/graph population fill `provenance`, `status.*`,
  `retrieval.*` — the schema already holds the columns, so **no migration**.
- `manifest.jsonl` compiler (a projection of the catalog) — trivial to add.
- FTS5 full-text search — named upgrade path from the current `LIKE` search.
