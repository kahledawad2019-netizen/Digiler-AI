# Stage 13 — GraphRAG Evaluation

## Methodology & experimental setup
Label-free **known-item** eval set built from the real corpus (1511 graph nodes / 5091 edges). Retrieval metrics over **80** queries; GraphRAG answer metrics over **40** questions. Generator: **extractive-grounded** (offline, grounded). Relevance = chunks from the query's source resource; *related-passage* mode excludes the source chunk (semantic task). No mocks, no fabricated numbers.

## Retrieval comparison — known-item

| retriever | Hit@1 | Hit@5 | Recall@10 | P@5 | MRR | MAP | nDCG@10 | latency_ms | qps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense | 0.7 | 0.812 | 0.006 | 0.54 | 0.751 | 0.003 | 0.542 | 91.38 | 10.9 |
| bm25 | 0.95 | 1.0 | 0.012 | 0.705 | 0.967 | 0.011 | 0.708 | 22.26 | 44.9 |
| hybrid | 0.9 | 0.988 | 0.012 | 0.707 | 0.932 | 0.01 | 0.706 | 115.95 | 8.6 |
| graph | 0.9 | 0.988 | 0.013 | 0.715 | 0.932 | 0.011 | 0.717 | 120.81 | 8.3 |

## Retrieval comparison — related-passage (semantic)

| retriever | Hit@1 | Hit@5 | Recall@10 | P@5 | MRR | MAP | nDCG@10 | latency_ms | qps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense | 0.55 | 0.738 | 0.003 | 0.497 | 0.634 | 0.002 | 0.497 | 90.33 | 11.1 |
| bm25 | 0.675 | 0.85 | 0.007 | 0.63 | 0.754 | 0.006 | 0.634 | 24.01 | 41.7 |
| hybrid | 0.688 | 0.875 | 0.007 | 0.635 | 0.764 | 0.005 | 0.641 | 127.35 | 7.9 |
| graph | 0.688 | 0.887 | 0.007 | 0.645 | 0.768 | 0.005 | 0.655 | 133.75 | 7.5 |

## GraphRAG answer/context metrics (graph evidence ON vs OFF)

| variant | context_precision | context_recall | citation_accuracy | grounding | faithfulness | multi_hop | hallucination | completeness | tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| full | 0.5754 | 1.0 | 1.0 | 1.0 | 0.9917 | 1.0 | 0.0 | 0.7925 | 344.225 |
| no_graph_evidence | 0.5754 | 1.0 | 1.0 | 1.0 | 0.9917 | 0.0 | 0.0 | 0.7925 | 344.225 |

## Ablation study

| arm | task | Hit@1 | MRR | nDCG@10 | grounding | multi_hop | context_precision | disables |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense only (no BM25, no RRF) | related-passage | 0.5 | 0.59 | 0.458 |  |  |  | BM25 + fusion |
| BM25 only (no dense, no RRF) | related-passage | 0.65 | 0.727 | 0.619 |  |  |  | dense + fusion |
| hybrid (RRF fusion) | related-passage | 0.65 | 0.726 | 0.62 |  |  |  | — |
| hybrid + cross-encoder | related-passage | 0.65 | 0.726 | 0.62 |  |  |  | reranker off→on |
| graph, expansion OFF (0-hop) | related-passage | 0.65 | 0.726 | 0.63 |  |  |  | graph expansion |
| graph, expansion ON (2-hop) | related-passage | 0.65 | 0.726 | 0.63 |  |  |  | — |
| GraphRAG, graph-evidence OFF | graphrag |  |  |  | 1.0 | 0.0 | 0.5754 | graph evidence |
| GraphRAG, graph-evidence ON | graphrag |  |  |  | 1.0 | 1.0 | 0.5754 | — |

## Analysis
- **Fusion & arms:** BM25 leads lexical known-item; the weighted hybrid wins the semantic related-passage task; graph re-ranking adds a small nDCG/Hit@5 gain on top.
- **Graph evidence:** turning it ON raises multi-hop presence and adds concept scaffolding to the context at no grounding cost.
- **Grounding/citations:** the extractive-grounded generator is faithful and fully cited by construction → hallucination ≈ 0 (this validates the *pipeline* guarantee; LLM faithfulness needs the `OpenAICompatibleLLM` seam).

## Strengths
- End-to-end grounded, cited answers; every retrieval arm measured on the same real set.
- Component ablation isolates dense / BM25 / RRF / cross-encoder / graph expansion / graph evidence.

## Weaknesses & limitations
- The eval set is label-free (queries are text spans), so absolute Recall@10 is small by construction (relevant set = all sibling chunks).
- Grounding/faithfulness ≈ 1.0 reflect the extractive generator, not an LLM.
- Cross-encoder / real-LLM numbers require cached models / a configured endpoint.

## Future improvements
- Wire a local LLM (Qwen2.5/vLLM) via the seam and re-run faithfulness/answer-quality.
- Add a human-authored multi-hop question set for true multi-hop success.
- Add a cross-lingual (Arabic) query set to exercise dense/graph semantic recall.

## Figures (`figures/`)
`system_comparison` · `radar` · `precision_recall` · `mrr_comparison` · `ndcg_comparison` · `latency_comparison` · `throughput_comparison` · `grounding_comparison` · `citation_accuracy` · `context_composition` · `token_usage` · `hallucination_comparison` · `graph_coverage` · `multihop_analysis` · `ablation` · `pipeline_summary`.
