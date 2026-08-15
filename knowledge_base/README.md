# Knowledge Base

This directory is where Digiler AI reads the learning materials it ingests, indexes,
and answers over. **The original academic corpus is intentionally excluded from this
public repository** for copyright and privacy reasons: it consists of third-party course
PDFs, lecture slides, textbooks, and notes that are not licensed for redistribution.

The platform is corpus-agnostic — you supply your own materials and run the ingestion
pipeline to build the indexes locally.

## Expected structure

```
knowledge_base/
  raw/            # your source materials, organised as track/course/module
    <track>/<course>/<module>/<file>
  derived/        # generated per-resource artifacts (created by ingestion)
  _incoming/      # drop-zone for new uploads
  _schemas/       # metadata schema (kept in the repo)
  _taxonomy/      # tracks / languages taxonomy (kept in the repo)
```

Everything under `raw/`, `derived/`, `_incoming/`, and `_quarantine/` is git-ignored.

## Supported resource formats

`.pdf`, `.pptx` / `.ppsx`, `.docx`, `.txt`, `.md`, `.ipynb` (documents);
`.vtt` / `.srt` (video transcripts); `.png` / `.jpg` (figures/images).

## How ingestion works

Add your files under `knowledge_base/raw/<track>/<course>/<module>/` (or upload them
through the app), then run the platform's ingestion, which performs:

```
Resource -> DIR (detect/identify/route) -> parent-child chunking -> metadata ->
embeddings (e5-small, 384-dim) -> Qdrant + BM25 -> concept graph
```

Programmatically, ingestion is driven by `IncrementalIngestor` (text/PDF/slides),
`VideoIngestor` (transcripts, timestamped), and `VisionIngestor` (figures). See the
project `README.md` and `docs/` for the full pipeline and the CLI (`ala init`).

## Why the corpus is not included

Publishing the raw materials would redistribute copyrighted educational content and
could expose private information. The **code, schemas, configuration, tests, evaluation
summaries, and figures** are published; the **data is not**. Bring your own corpus to
reproduce the system end to end.
