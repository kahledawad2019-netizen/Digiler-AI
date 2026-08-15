# Stage 14 — Research Mode + Web Search + Knowledge Growth

A confidence-gated extension of GraphRAG: when the Knowledge Base cannot
confidently answer, Research Mode searches the web, scores + ranks sources, parses
them into the **existing** Resource Fabric, merges web evidence with KB evidence,
answers, and — on user approval — grows the KB through the **existing** ingestion
pipeline so new knowledge is immediately searchable. Fully **additive**; no
pipeline is duplicated. Package: [`src/ala/research/`](../src/ala/research/).

## Architecture

```
question → GraphRAG(KB) → ConfidenceEstimator
                              │ score ≥ threshold → answer from KB
                              │ score < threshold ↓
                        WebSearchAdapter (provider) → SourceQualityEvaluator
                              → WebDocumentParser → ResearchEvidenceMerger(KB+web)
                              → GraphRAG answer → "save to KB?" 
                              → approved? IncrementalIngestor
                                  (ingest → chunk → embed → Qdrant → BM25 → graph)
```

## Components

1. **ResearchModeController** ([controller.py](../src/ala/research/controller.py)) —
   orchestrates the whole flow; reuses the GraphRAG pipeline's own
   context/prompt/generator/citations for the merged answer (no regeneration logic
   duplicated) and logs every session.
2. **ConfidenceEstimator** ([confidence.py](../src/ala/research/confidence.py)) —
   a single [0,1] score + level from real signals (semantic similarity, evidence
   agreement, BM25 strength — the signals that actually discriminate in/out-of-corpus;
   citation/support/graph are ~constant under the extractive generator and excluded).
3. **WebSearchAdapter** ([search.py](../src/ala/research/search.py)) — provider
   abstraction, one active by config: `duckduckgo` (no key), `tavily`, `google`
   (key + cx), `local` (offline folder), `disabled` (default). Real stdlib-`urllib`
   HTTP, fail-soft.
4. **SourceQualityEvaluator** ([sources.py](../src/ala/research/sources.py)) —
   authority · freshness · educational value · spam · domain quality · citation
   quality → a **trust** score; ranks and **de-duplicates**; gates by `min_source_trust`.
5. **WebDocumentParser** ([parser.py](../src/ala/research/parser.py)) — downloads +
   cleans HTML (BeautifulSoup) / PDF (pypdf) / text, saves Markdown under the
   research track so the **existing** loaders/DIR handle it.
6. **ResearchEvidenceMerger** ([merge.py](../src/ala/research/merge.py)) — merges KB
   and web evidence into one `EvidencePackage`; source attribution + citations never
   lost (web items carry URL/domain/provider provenance).
7. **User approval** — `research(question, approve=callback)`; nothing is saved
   unless the callback returns `True` (or `auto_approve`).
8. **IncrementalIngestor** ([ingest.py](../src/ala/research/ingest.py)) — one file
   through the real pipeline: ingestion → chunking → embedding (index model) →
   Qdrant upsert → BM25 add → concept-graph link. No full rebuild. Stores are
   injected (DI) so production and the isolated benchmark share one code path.
9. **ResearchSessionLog** ([session.py](../src/ala/research/session.py)) — append-only
   JSONL audit trail (searches, sources, confidence, approval, ingestion, stats).

## CLI

```powershell
ala research "what is a convolutional neural network"        # KB-confident → answers directly
ala research "latest advances in retrieval augmented generation" --save   # low conf → web + grow KB
ala research --benchmark
```

## Configuration (`config/platform.yaml → research`)

`web_search.provider` (+ `api_key`/`google_cx`), `max_results`, `top_sources`,
`min_source_trust`, `auto_approve`, `research_track`/`research_course`, and
`confidence.{threshold, high_threshold, low_threshold, bm25_ref, weights}`.

## Benchmark (real corpus, offline — no mocks) — `reports/stage14_research/`

**Confidence gate** (10 in-corpus vs 10 out-of-corpus questions, real GraphRAG):

| metric | value |
|---|---|
| in-corpus mean confidence | 0.769 |
| out-of-corpus mean confidence | 0.604 |
| gap | 0.164 |
| separation **AUC** | **0.96** |
| gate accuracy @ 0.70 | **0.90** |
| out-of-corpus correctly escalated | 0.90 |
| in-corpus false-escalated | 0.10 |

**Source quality:** 8 representative sources, 1 duplicate detected, 3 selected;
trust ordering pytorch.org 0.78 > scikit-learn 0.72 > arxiv 0.68 > … > spam 0.0.
**Evidence merge:** KB (6) + web (1) items, all cited, web provenance preserved.
**Incremental indexing** (real doc, isolated index): 1 child chunk, **searchable**,
per-stage ms — ingest 76 · chunk 5 · embed 1758 (e5 CPU) · **Qdrant 40 · BM25 3 ·
graph 57** → the index update itself is ~100 ms; embedding dominates.

## Visualizations (`figures/`)

`research_pipeline` · `confidence_distribution` · `confidence_histogram` ·
`gate_outcomes` · `source_authority` · `web_vs_kb` ·
`incremental_indexing_timeline` · `knowledge_growth`.

## Design decisions

- **Confidence calibration is honest:** the estimator ranks in/out-of-corpus with
  AUC 0.96; the absolute threshold (0.70) was calibrated on the real signal
  distributions, not guessed. Non-discriminative signals were *removed* rather than
  left to inflate scores.
- **No duplicate pipeline:** web documents become normal Markdown files and flow
  through the exact ingestion → chunking → embedding → index path every other
  resource uses.
- **Safety:** the benchmark/tests ingest into an **isolated** index (temp dirs +
  `:memory:` Qdrant) so the production index is never mutated; growth only happens
  on explicit approval.

## Tests

[`tests/test_research.py`](../tests/test_research.py) — confidence (high/low gate),
source ranking + duplicate detection + selection, evidence merge (provenance +
citations), parser (local HTML → Markdown), providers (disabled/local),
**incremental ingestion on the real pipeline** (searchable), and the **full offline
controller flow** (local provider → merge → answer → session log). Full suite
**165 passed**.

## Limitations (honest)

- Web search/parse need network; the benchmark runs offline, so source-quality is
  the evaluator's deterministic output over representative sources (not a live crawl)
  and merge uses a locally-injected document. The providers are real and network-ready.
- The confidence threshold is corpus-calibrated on 20 questions; **AUC (ranking)**
  is the robust, threshold-independent metric — the absolute threshold should be
  re-tuned per corpus.
- Incremental embedding latency is dominated by the e5 CPU forward pass; the index
  mutation (Qdrant/BM25/graph) is ~100 ms.
- Concept-graph growth is an incremental *link* (new resource → concepts) — it does
  not recompute global co-occurrence edges; a periodic full rebuild remains optional.

## Extension hooks (designed, not implemented)

- **Citation Explorer (15):** `CitationRecord`/web-item metadata already carry
  url/domain/page/slide/timestamp.
- **Student Model (18) / Analytics (19):** the `ResearchSessionLog` is the event
  source for knowledge-growth analytics.
- **Video (16) / Vision (17):** new modalities become `LearningResource`s and reuse
  `IncrementalIngestor` unchanged.
- **Function Calling (23) / Agents (22):** `ResearchModeController.research()` is a
  single tool entry point.
