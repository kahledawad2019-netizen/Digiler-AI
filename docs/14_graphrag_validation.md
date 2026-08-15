# Stage 13 — GraphRAG Evaluation

A publication-quality evaluation framework comparing every retrieval method and
the GraphRAG generation pipeline on the **real corpus only** — no mocks, no
synthetic data, no fabricated numbers. Every value comes from a real
retriever/pipeline execution. Fully **additive**: reuses `ala.retrieval.evaluation`
(metrics/evalset) and every retriever; adds only the orchestrator + figures.

Package: [`src/ala/rag/evaluation.py`](../src/ala/rag/evaluation.py) (suite +
ablation + metrics) and [`evalviz.py`](../src/ala/rag/evalviz.py) (16 figures).
CLI: `ala graphrag-eval --n 80 --n-rag 40` → `reports/stage13_graphrag_eval/`.

## Methodology & experimental setup

- **Data:** the label-free **known-item** eval set (Stage 8), built directly from
  the corpus — a query is a word span from a child chunk; the *relevant set* is
  every chunk of that chunk's source resource. **related-passage** mode removes
  the source chunk (a semantic "find the resource's other passages" task).
- **Systems:** Dense · BM25 · Hybrid · Graph (retrieval metrics); **GraphRAG**
  (answer/context metrics, graph-evidence ON vs OFF).
- **Scale:** retrieval over **80** queries, GraphRAG over **40** questions,
  graph 1,511 nodes / 5,091 edges. Generator: **extractive-grounded** (offline).

## Metrics

Retrieval: Recall@k · Precision@k · Hit@k · MRR · MAP · nDCG@10 · latency · qps.
Answer/context: Context Precision · Context Recall · Citation Accuracy ·
Grounding · Faithfulness · Multi-hop presence · Hallucination rate · Answer
Completeness · context tokens.

## Results — retrieval (related-passage, semantic)

| system | Hit@1 | Hit@5 | MRR | nDCG@10 | latency | qps |
|---|---|---|---|---|---|---|
| Dense | 0.550 | 0.738 | 0.634 | 0.497 | 90 ms | 11.1 |
| BM25 | 0.675 | 0.850 | 0.754 | 0.634 | **24 ms** | **41.7** |
| Hybrid | 0.688 | 0.875 | 0.764 | 0.641 | 127 ms | 7.9 |
| **Graph** | 0.688 | **0.887** | **0.768** | **0.655** | 134 ms | 7.5 |

Known-item (lexical): BM25 leads (Hit@1 **0.95**), Hybrid/Graph 0.90, Dense 0.70.

## Results — GraphRAG (graph evidence ON vs OFF)

| variant | ctx precision | ctx recall | citation acc | grounding | faithfulness | multi-hop | hallucination | completeness |
|---|---|---|---|---|---|---|---|---|
| **graph-evid ON** | 0.575 | 1.00 | 1.00 | 1.00 | 0.992 | **1.00** | 0.00 | 0.79 |
| graph-evid OFF | 0.575 | 1.00 | 1.00 | 1.00 | 0.992 | **0.00** | 0.00 | 0.79 |

## Ablation study (related-passage nDCG@10, n=40)

| arm | disables | nDCG@10 |
|---|---|---|
| dense only | BM25 + fusion | 0.458 |
| BM25 only | dense + fusion | 0.619 |
| hybrid (RRF) | — | 0.620 |
| hybrid + cross-encoder | reranker off→on | 0.620 |
| graph, expansion OFF (0-hop) | graph expansion | 0.630 |
| graph, expansion ON (2-hop) | — | 0.630 |
| GraphRAG, graph-evidence OFF | graph evidence | multi-hop 0.0, grounding 1.0 |
| GraphRAG, graph-evidence ON | — | multi-hop 1.0, grounding 1.0 |

The cross-encoder model **loaded and ran** (real number) — it does not help on
this lexical corpus. Graph expansion 0-hop == 2-hop (consistent with Stage 11).

## Analysis

- **Biggest lever is BM25** (dense-only 0.458 → +BM25 0.619). Fusion (+0.001) and
  graph re-ranking (+0.010) add small, real gains; the cross-encoder adds nothing
  here — the corpus is highly technical and text-derived queries are near the
  lexical ceiling (a finding held consistently since Stage 8, never tuned away).
- **Graph is the best single retriever on the semantic task** (nDCG 0.655).
- **Graph evidence** cleanly turns multi-hop reasoning on (0.0 → 1.0) at **zero**
  grounding/faithfulness cost — it adds a concept scaffold, not noise.
- **Grounding/faithfulness ≈ 1.0, hallucination ≈ 0.0** — the extractive-grounded
  generator is grounded by construction; this validates the *pipeline's*
  guarantee, not an LLM's fluency.

## Strengths

- One real eval set across all systems; component ablation isolates dense / BM25 /
  RRF / cross-encoder / graph expansion / graph evidence.
- End-to-end grounded, cited answers with a measured hallucination rate of 0.

## Weaknesses & limitations (honest)

- Label-free eval → absolute Recall@10 is small by construction (relevant set =
  all sibling chunks); metrics are comparative, not absolute quality.
- Grounding/faithfulness reflect the **extractive** generator, not an LLM.
- Multi-hop presence measures *availability* of graph relations in context, not
  success on a curated multi-hop question set.
- Metadata could not be fully "removed" without breaking citations; its value is
  reported as citation-locator coverage rather than an nDCG delta.

## Future improvements

- Wire a local **Qwen2.5 / vLLM** via the `OpenAICompatibleLLM` seam and re-run
  faithfulness + answer quality under a real generator.
- Add a **human-authored multi-hop** question set and a **cross-lingual (Arabic)**
  query set to exercise dense/graph semantic recall.

## Visualizations (`figures/`, all real)

`system_comparison` · `radar` · `precision_recall` (Hit@k) · `mrr_comparison` ·
`ndcg_comparison` · `latency_comparison` · `throughput_comparison` ·
`grounding_comparison` · `citation_accuracy` · `context_composition` ·
`token_usage` · `hallucination_comparison` · `graph_coverage` ·
`multihop_analysis` · `ablation` · `pipeline_summary`.

## Tests

[`tests/test_graphrag_eval.py`](../tests/test_graphrag_eval.py) — metric maths
(context precision/recall, grounding, faithfulness, hallucination detection,
aggregation). Full suite **156 passed**.
