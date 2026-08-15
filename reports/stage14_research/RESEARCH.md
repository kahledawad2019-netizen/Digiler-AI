# Stage 14 — Research Mode: Benchmark

## Confidence gate (in-corpus vs out-of-corpus, real GraphRAG)

- in-corpus mean confidence **0.7688** vs out-of-corpus **0.6043** (gap **0.1645**)
- separation AUC **0.96** · gate accuracy **0.9** (threshold 0.7)
- research-triggered: in-corpus 0.1 · out-of-corpus 0.9

## Source quality (real evaluator over representative sources)

8 sources · **1** duplicate(s) detected · **3** selected (trust ≥ min).

| domain | trust | authority | spam | dup |
|---|---|---|---|---|
| pytorch.org | 0.775 | 0.95 | 0.0 |  |
| scikit-learn.org | 0.715 | 0.95 | 0.0 |  |
| arxiv.org | 0.675 | 1.0 | 0.0 |  |
| stackoverflow.com | 0.635 | 0.75 | 0.0 |  |
| medium.com | 0.595 | 0.5 | 0.0 |  |
| en.wikipedia.org | 0.57 | 0.85 | 0.0 |  |
| buy-cheap-degrees.biz | 0.0 | 0.45 | 1.0 |  |
| en.wikipedia.org | 0.57 | 0.85 | 0.0 | dup |

## Evidence merge (KB + web, provenance preserved)

- KB items **6** + web items **1** merged · all cited: **True** · web provenance kept: **True**

## Incremental indexing (real pipeline, isolated index)

New resource `research.web.web.gradient-boosting-ensembles` · 1 child chunks · **searchable: True** · total **1939.0 ms**.

| stage | ms |
|---|---|
| ingest | 76.1 |
| chunk | 5.2 |
| embed | 1758.0 |
| qdrant | 39.6 |
| bm25 | 3.0 |
| graph | 57.0 |

## Honest notes
- Web search/parse require network; the providers are real but the benchmark runs offline, so source-quality is the evaluator's deterministic output over representative inputs (not a live crawl) and merge uses a real document injected locally.
- Incremental indexing runs the real chunk→embed→Qdrant→BM25→graph code on a real document into an isolated index (production untouched); latencies are real.
