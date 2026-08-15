# Stage 15 — Citation Explorer: Report

Real corpus, **10 queries**, **230 citations** indexed.

## Citation accuracy

| metric | value |
|---|---|
| resolvable rate (deep link works) | 1.0 |
| locator coverage (page/slide/timestamp) | 0.875 |
| mean citation confidence | 0.8941 |
| by source type | {'pdf': 70, 'notebook': 10, 'concept': 150} |
| by kind | {'chunk': 80, 'concept': 150} |

## Clickable explorer
- `example_explorer.html` — self-contained HTML: filter by kind/source-type, click any citation to open the PDF page / slide / video timestamp / web URL.

## Figures (`figures/`)
`citation_distribution` · `citation_accuracy` · `evidence_composition` · `citation_flow`.

## Honest notes
- *Resolvable* = the cited resource's raw file exists and a deep link (with page/slide/timestamp fragment) can be built; it does not re-verify that the PDF page shows the exact sentence (that needs a PDF renderer). Locator coverage is the fraction of chunk citations that carry a page/slide/timestamp.
- Slide/notebook fragments (`#slide=`, cells) are conventions most viewers ignore; the file still opens. Video timestamps use `#t=` (browser/YouTube convention).
