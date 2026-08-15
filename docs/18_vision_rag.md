# Stage 17 — Vision RAG

Makes figures, tables, diagrams, charts and screenshots **retrievable** by turning
them into text-carrying `IMAGE_CAPTION` blocks (caption + OCR + structured
metadata) that flow through the *existing* pipeline (DIR → embedding → concept
graph → GraphRAG) and cite by page. Fully **additive** — image evidence reuses the
same retriever, Evidence Package and Citation Explorer as text. Package:
[`src/ala/vision/`](../src/ala/vision/).

## Two paths

1. **FigureExtractor (offline-real, the star)** — lecture PDFs already carry
   `Figure 3: …` / `Table 1: …` captions as text. This lifts them (with the source
   **page** from the chunk anchor), classifies the kind (figure / table / diagram /
   chart), and makes each an individually searchable, page-cited `IMAGE_CAPTION`
   block — **no vision model required**.
2. **ImageLoader (standalone images)** — `.png/.jpg/…` → caption (BLIP) + OCR
   (tesseract) → an `IMAGE_CAPTION` block; cross-modal vectors via CLIP. These
   backends are **config-selected seams**; offline, an image still yields an honest
   minimal block (`[image] <name>`), never a fabricated caption.

## Architecture

```
figure caption (corpus text)     standalone image (.png)
        │                                │  VisionAdapter
   FigureExtractor                 Captioner(BLIP) + ImageOCR(tesseract) + Encoder(CLIP)
        │  page anchor                   │  kind, caption, ocr_text
        ▼                                ▼
   FigureArtifactLoader (.figures.jsonl)   ImageLoader (.png/…)
        └──────────────┬─────────────────┘
                       ▼  IMAGE_CAPTION block (page anchor / char anchor)
        VisionIngestor → IncrementalIngestor.ingest_resource
             chunk → embed → Qdrant → BM25 → concept graph
                       ▼
        GraphRAG / retriever / Citation Explorer (page-anchored image citation)
```

## Components

- **FigureExtractor** ([figures.py](../src/ala/vision/figures.py)) — regex caption
  detection over corpus text; kind classification; decimal figure numbers; dedupe.
- **VisionEncoder / Captioner / ImageOCR** ([encoder.py](../src/ala/vision/encoder.py))
  — CLIP / BLIP / tesseract real backends behind interfaces; `disabled` defaults;
  missing deps degrade to empty, never crash.
- **VisionAdapter** ([adapter.py](../src/ala/vision/adapter.py)) — image → `ImageAsset`
  (caption + OCR + kind from filename hints).
- **ImageLoader / FigureArtifactLoader** ([loader.py](../src/ala/vision/loader.py)) —
  standard `BaseLoader`s emitting `IMAGE_CAPTION` blocks (char / page anchors).
- **VisionIngestor** ([ingest.py](../src/ala/vision/ingest.py)) — `ingest_figures(rid)`
  and `ingest_image(path)`; reuses `IncrementalIngestor.ingest_resource`.

## CLI

```powershell
ala vision --figures technical.applied-dl.w06.practical-dl-lec6-1   # index that resource's figures
ala vision --image diagram.png --title "CNN architecture"
ala vision --benchmark
```

## Configuration (`config/platform.yaml → vision`)

`encoder` · `captioner` · `ocr` · `clip_model` · `blip_model` ·
`min_caption_words` · `max_caption_chars` · `track` · `course`.

## Benchmark (real corpus, isolated index — no mocks) — `reports/stage17_vision/`

Scanned **140** resources → **23** had captioned figures → **1,271 figures**
extracted → **283** image blocks indexed. By kind: figure 134 · table 111 · chart
36 · diagram 2.

| figure retrieval (caption span → its own figure, n=60) | value |
|---|---|
| **Hit@1** | **0.767** |
| Hit@3 | **0.950** |
| MRR | 0.861 |
| mean ingest / resource | 113 ms |

**Page-anchored image citation:** locator `p.1`, link `…/…figures.jsonl#page=1`
(resolvable) — a figure is retrievable *and* citable to its page, and lights up the
Citation Explorer.

## Visualizations (`figures/`)

`vision_pipeline` · `figure_type_distribution` · `retrieval_quality` · `ingest_timeline`.

## Tests

[`tests/test_vision.py`](../tests/test_vision.py) — figure/table/diagram extraction
(kinds, decimals, bare-reference skip, dedupe), artifact + image loaders
(page-anchored `IMAGE_CAPTION` blocks), backend selection, kind-from-filename, and
a **real isolated figure-ingestion** integration. Full suite **188 passed**.

## Limitations (honest)

- The offline path is **caption-and-embed** over the corpus text layer — genuinely
  useful and evaluated, but it indexes figures that have a *textual* caption. True
  **cross-modal retrieval (CLIP image vectors)** and **image captioning (BLIP)** and
  **OCR of caption-less diagrams** are real, config-selected seams that need the
  optional vision deps (open_clip / transformers / pytesseract — not installed here).
- Figures without any inline caption are skipped (no fabricated descriptions).
- Retrieval is a label-free caption-span task; Hit@1 < 1.0 mostly reflects
  near-duplicate captions ("diagram of a neural network").
- Region/bbox anchors within a page are a future extension (the anchor currently
  carries page, not pixel region).

## Extension hooks

- **CLIP cross-modal** plugs in as a second embedding space (image vectors indexed
  alongside text) — the `VisionEncoder` seam is ready.
- **GraphRAG** already consumes these blocks (they are ordinary evidence); a diagram
  can be a concept's `example_of`.
- **Student Model (18):** "figures viewed" reference these resource ids + pages.
