# Milestone — Production Corpus Import (`Basic_knowladg` → managed KB)

**Goal:** organize a new 288-file / 848 MB corpus into the managed Knowledge
Base and run the **existing** ingestion + chunking pipeline over it — without
redesigning or modifying any completed component. Only additive, backward-compatible
extensions were used.

## What was added (all additive)

1. **Taxonomy extension** ([config/taxonomy/tracks.yaml](../config/taxonomy/tracks.yaml)) —
   four new courses under the `technical` track: `agentic-ai`, `applied-dl`,
   `applied-stats`, `excel-ai` (alongside existing `dmv`, `aiml`, `eng`). Only
   track + course ids are validated, so week/session folders map to module slugs
   at ingest time.
2. **`.ppsx` support** — `.ppsx` is the same OOXML format as `.pptx`, so the
   existing `PptxLoader` handles it; the extension was added to the loader,
   discovery, and `ingestion.supported_extensions`. **No new loader.**
3. **`CorpusImporter`** ([src/ala/ingestion/importer.py](../src/ala/ingestion/importer.py)) —
   copies (never moves/modifies) the drop folder into
   `knowledge_base/raw/<track>/<course>/<module>/<file>`, inferring
   track/course/module from the source structure (stripping Google-Takeout
   wrapper folders, extracting `weekN` / `sessionN`), with disposition rules.

## Disposition rules (why each file went where)

| Disposition | Applies to | Rationale |
|---|---|---|
| **COPY** | pdf, pptx, **ppsx**, docx, txt, md, html, ipynb | prose — ingested by the pipeline |
| **COPY_DATASET** | xlsx, xls, csv, sql | data, not prose — copied + registered `role=dataset`, tracked with provenance but **not chunked/embedded** (per the approved redesign) |
| **QUARANTINE** | `client_secret_*.json` | credential — copied to `_quarantine/`, **never ingested** (security) |
| **SKIP** | zip, mhtml, crdownload, `*.ipynb.txt` | archives, near-duplicate saved-web dumps, aborted downloads, notebook shadow copies |

Import result: **206 copy · 51 dataset · 1 quarantine · 30 skip** (= 288).
Datasets are de-duplicated by sha256 (repeated CSVs across Excel weeks are
detected automatically by the existing change-detector).

## Pipeline applied (unchanged, existing code)

```
CorpusImporter (copy + classify)
   ↓
ingest-dir --chunk:
   Discovery → Validation → Loader → Extraction → Normalization →
   Language → Structural → Academic → Enrichment → Packaging →
   Registry Commit → Catalog → Parent-Child Chunking → Chunk Metadata
```

Every prose resource passes through the full 10-stage ingestion and then
parent-child chunking; each becomes a `LearningResource` + `ResourcePackage` +
chunk set under `knowledge_base/derived/<resource_id>/`.

## CLI
```powershell
ala import-corpus <source> [--dry-run]     # organize into the managed KB
ala ingest-dir --chunk                     # ingest + chunk the managed tree
ala stats                                  # catalog totals by course/type/status
```

## Notes / honest limitations
- **Datasets & spreadsheets** are intentionally not text-chunked — they are data,
  not learning prose. They are registered (tracked, hashed, provenanced) so
  "nothing enters the KB without metadata", and are available to future
  dataset-aware tooling.
- **Scanned / image PDFs** (from the original audit) still extract 0 blocks and
  are flagged "OCR may be needed" by the extraction stage — surfaced, not hidden.
  OCR is a later milestone.
- **`.mhtml` / `.zip`** are skipped for now (saved-web duplicates and archives);
  adding an unpack/mhtml adapter is a future additive loader if needed.
