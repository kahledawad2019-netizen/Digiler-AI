# Stage 17 — Vision RAG: Benchmark

Scanned **140** corpus resources → **23** had captioned figures/tables → **1271 figures** → **283 image blocks** indexed.

By kind: {'figure': 134, 'chart': 36, 'table': 111, 'diagram': 2}

## Figure retrieval (caption span → its own figure)

| metric | value |
|---|---|
| queries | 60 |
| Hit@1 | **0.7667** |
| Hit@3 | 0.95 |
| MRR | 0.8608 |
| mean ingest / resource | 81.1 ms |

## Page-anchored image citation
- locator **p.1** · link `file:///C:/Windows/Temp/ala_vision_nsnmfqea/raw/vision/figures/fig/technical-applied-dl-w01-practical-dl-lab1-1.figures.jsonl#page=1` (resolvable True)

## Figures (`figures/`)
`vision_pipeline` · `figure_type_distribution` · `retrieval_quality` · `ingest_timeline`.

## Honest notes
- The offline path is **caption-and-embed**: real figure/table captions from the corpus text layer become searchable `IMAGE_CAPTION` blocks (page-anchored). True cross-modal retrieval (CLIP image vectors) and image captioning (BLIP) are real, config-selected seams that require the optional vision deps (not installed here).
- Figures without an inline text caption (a bare `Figure 1` reference) are skipped — only genuinely described figures/tables are indexed. Retrieval is a label-free caption-span task.
