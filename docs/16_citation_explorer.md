# Stage 15 — Citation Explorer

A unified, navigable view over the citations the pipeline already produces. It
resolves every citation to a **clickable deep link** (PDF page, slide, notebook,
video timestamp, web URL, or concept/graph origin), groups them by source,
supports filtering, and exports a self-contained HTML explorer plus a
citation-accuracy report. Fully **additive** — it reads the Evidence Package,
graph evidence and web evidence; it changes none of them. Package:
[`src/ala/explorer/`](../src/ala/explorer/).

## Architecture

```
EvidencePackage (chunks + graph_evidence + web items)
        │
   CitationExplorer ── assigns C# (chunk) / K# (concept) / W# (web)
        │
   CitationResolver ── catalog → raw file path → clickable link + fragment
        │              (#page=N · #slide=N · #t=SECONDS · web URL · concept:<id>)
        ▼
   CitationIndex ──► filter(kind/source_type/resource/confidence)
                 ──► sources()  (source explorer)
                 ──► stats()    (accuracy)
                 ──► HTML export (clickable browser)
```

## Components

- **CitationExplorer** ([explorer.py](../src/ala/explorer/explorer.py)) — builds a
  `CitationIndex` of `CitationNode`s from any `EvidencePackage` (KB, GraphRAG or
  Research merged): chunk (`C#`), concept/graph (`K#`), web (`W#`).
- **CitationResolver** ([resolver.py](../src/ala/explorer/resolver.py)) — resolves
  the source resource via the catalog and builds the deep link + fragment per
  modality; concept citations link to their graph node, web to their URL.
- **CitationIndex** ([models.py](../src/ala/explorer/models.py)) — filtering
  (evidence filtering), source grouping (source explorer) and accuracy stats.
- **HTML explorer** ([html.py](../src/ala/explorer/html.py)) — a self-contained,
  inline-CSS/JS page: clickable citations, filter chips (by kind / source type),
  confidence bars, a source sidebar. No external assets.
- **CitationExplorerService** ([service.py](../src/ala/explorer/service.py)) — wires
  GraphRAG + catalog; `explore(query)` and `export_html(query, path)`.

## Modalities (clickable evidence)

| kind | source type | deep link |
|---|---|---|
| chunk | pdf | `file://…/file.pdf#page=N` |
| chunk | slide | `file://…/file.pptx#slide=N` |
| chunk | video | `file://…#t=SECONDS` |
| chunk | notebook | `file://…/file.ipynb` |
| web | web | the source URL |
| concept | concept | `concept:<id>` (graph navigation) |

## CLI

```powershell
ala citations "what is a convolutional neural network"                 # list resolved citations
ala citations "explain gradient descent" --html out/explorer.html      # clickable HTML
ala citations --benchmark
```

## Benchmark (real corpus, 10 queries — no mocks) — `reports/stage15_citation_explorer/`

| metric | value |
|---|---|
| citations indexed | **230** (80 chunk + 150 concept) |
| by source type | pdf 70 · notebook 10 · concept 150 |
| **resolvable rate** (deep link works) | **1.00** |
| **locator coverage** (page/slide/timestamp) | **0.875** |
| mean citation confidence | 0.894 |

Every citation resolves to a real file / graph node; 87.5 % of chunk citations
carry a page/slide/timestamp (the rest are notebooks, which have no page number).
A clickable `example_explorer.html` is exported (13 live deep links).

## Visualizations (`figures/`)

`citation_distribution` (by source type + kind) · `citation_accuracy`
(resolvable / locator / confidence) · `evidence_composition` (chunk/concept/web) ·
`citation_flow` (citations → sources bipartite).

## Tests

[`tests/test_explorer.py`](../tests/test_explorer.py) — resolver (PDF deep link,
concept + web links, unresolved), index kinds/locators/stats, filtering + source
grouping, `max_citations`, clickable HTML, and a real-corpus integration test.
Full suite **172 passed**.

## Limitations (honest)

- **No slide/video citations yet** — the current corpus is PDF + notebook, so
  those code paths exist but are unexercised until Stage 16 (Video) / slide decks
  surface slide numbers.
- *Resolvable* means the raw file exists and a fragment link can be built; it does
  **not** re-render the PDF to verify the exact sentence is on that page (that
  needs a PDF renderer). Locator coverage < 1.0 because notebook chunks lack pages.
- `#slide=` / notebook-cell fragments are conventions most viewers ignore; the file
  still opens at the top.

## Extension hooks

- **Video (16):** video chunks arrive with `timestamp` → `#t=` links light up
  automatically (no explorer change).
- **Vision RAG (17):** image citations become a new `source_type` with a region
  locator, resolved the same way.
- **Dashboard (19):** `CitationIndex.stats()` / `sources()` feed the evidence
  browser panel; the HTML explorer embeds directly.
