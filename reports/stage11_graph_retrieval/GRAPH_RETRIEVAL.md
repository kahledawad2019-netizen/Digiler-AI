# Stage 11 — Graph Retrieval: Benchmark

Real corpus: **1511 nodes / 5091 edges / 131 concepts**; **100 queries**.

## Ranking comparison — known-item (find the source resource)

| retriever | n | Hit@1 | Hit@5 | Hit@10 | Recall@10 | P@5 | MRR | MAP | nDCG@10 | latency_ms | qps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | 100 | 0.9 | 0.97 | 0.98 | 0.017 | 0.718 | 0.926 | 0.015 | 0.713 | 121.79 | 8.2 |
| graph | 100 | 0.9 | 0.97 | 0.98 | 0.018 | 0.728 | 0.926 | 0.015 | 0.726 | 119.25 | 8.4 |

## Ranking comparison — related-passage (semantic: find the *other* passages)

| retriever | n | Hit@1 | Hit@5 | Hit@10 | Recall@10 | P@5 | MRR | MAP | nDCG@10 | latency_ms | qps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| hybrid | 100 | 0.71 | 0.88 | 0.92 | 0.013 | 0.654 | 0.778 | 0.01 | 0.653 | 113.2 | 8.8 |
| graph | 100 | 0.71 | 0.89 | 0.92 | 0.013 | 0.668 | 0.782 | 0.01 | 0.669 | 115.88 | 8.6 |

## Graph-specific metrics

| metric | value |
|---|---|
| concept-link coverage | 1.0 |
| graph recall (gold reached via expansion) | 1.0 |
| avg seed concepts / query | 7.87 |
| avg expanded concepts / query | 60.0 |
| node coverage | 0.208 |
| edge coverage | 0.313 |
| concept coverage | 0.969 |
| graph-evidence→gold rate | 0.3 |
| mean latency (ms) | 116.21 |
| throughput (qps) | 8.6 |
| hop distribution | {'0': 100} |

## Traversal-depth ablation (related-passage)

| hops | Hit@1 | Hit@5 | MRR | nDCG@10 | latency_ms |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.71 | 0.89 | 0.782 | 0.669 | 115.89 |
| 2 | 0.71 | 0.89 | 0.782 | 0.669 | 125.39 |
| 3 | 0.71 | 0.89 | 0.782 | 0.669 | 125.41 |

## Example traversal — "convolutional neural network"

Seed concepts: cnn, neural-network, image-classification, normalization-db, machine-learning, deep-learning, activation-function, optimizer.  Expanded 60 concepts over 1 hops in 124.7 ms.

| expanded concept | hop | relationship | score |
|---|---|---|---|
| Convolutional Neural Network | 0 | seed | 1.0 |
| Neural Network | 0 | seed | 0.6 |
| Image Classification | 0 | seed | 0.6 |
| Database Normalization | 0 | seed | 0.6 |
| Machine Learning | 0 | seed | 0.6 |
| Deep Learning | 0 | seed | 0.6 |
| Activation Function | 0 | seed | 0.6 |
| Optimizer | 0 | seed | 0.6 |

## Figures (`figures/`)
- `ranking_comparison.png` · `graph_coverage.png` · `hop_distribution.png`
- `traversal_example.png` · `retrieved_graph.png` · `concept_expansion.png`
- `node_importance.png` · `edge_importance.png` · `evidence_composition.png`
- `traversal_depth_comparison.png` · `latency.png`
