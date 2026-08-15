# Stage 4 — Embedding Pipeline: Benchmark & Evaluation

Sampled **300 real child chunks** across **7 courses** from the ingested corpus.

## Model comparison

| model | dim | n | embed_s | texts/s | compute_mb | bytes/vec | query_ms | coherence | nn_purity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hashing | 384 | 300 | 6.129 | 48.9 | 3.6 | 1536 | 3.59 | 0.2528 | 0.6967 |
| minilm | 384 | 300 | 5.608 | 53.5 | 4.0 | 1536 | 44.08 | 0.2847 | 0.6267 |
| e5-small | 384 | 300 | 13.934 | 21.5 | 4.3 | 1536 | 72.83 | 0.0724 | 0.74 |

Columns: `embed_s` steady-state embed time (model load excluded via warmup) · `texts/s` throughput · `compute_mb` peak Python allocation during embed · `bytes/vec` storage per vector · `query_ms` mean single-query latency · `coherence` = mean cosine(same-resource) − mean cosine(different-resource) · **`nn_purity`** = fraction of chunks whose nearest neighbour shares the same resource — a rank-based quality signal robust to each model's absolute cosine scale (the fairest cross-model comparison here). Latency reflects a CPU-only sandbox; a GPU would be 1–2 orders of magnitude faster.

## Figures

- ![model_comparison](figures/model_comparison.png)
- ![pca_hashing](figures/pca_hashing.png)
- ![tsne_hashing](figures/tsne_hashing.png)
- ![cosine_hashing](figures/cosine_hashing.png)
- ![dist_hashing](figures/dist_hashing.png)
- ![pca_minilm](figures/pca_minilm.png)
- ![tsne_minilm](figures/tsne_minilm.png)
- ![cosine_minilm](figures/cosine_minilm.png)
- ![dist_minilm](figures/dist_minilm.png)
- ![pca_e5-small](figures/pca_e5-small.png)
- ![tsne_e5-small](figures/tsne_e5-small.png)
- ![cosine_e5-small](figures/cosine_e5-small.png)
- ![dist_e5-small](figures/dist_e5-small.png)
