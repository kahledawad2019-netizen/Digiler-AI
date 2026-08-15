# Stage 11 — Graph Retrieval

A graph-aware retrieval layer that sits **on top of** the hybrid retriever
(Stage 7) and the concept graph (Stage 10) and folds its output into the same
Evidence Package (Stage 9). Fully **additive** — no existing module changed;
`GraphRetriever` implements the same `Retriever` protocol, so it drops into the
pipeline and the evaluation harness unchanged.

## Architecture

```
                    query
                      │
             ┌────────▼─────────┐
             │  HybridRetriever  │  (dense e5 + BM25 + RRF)  →  candidate chunks
             └────────┬─────────┘
                      │  seed resources (+ query text)
             ┌────────▼─────────┐
             │ QueryConceptLinker│  query aliases ∪ seed-resource concepts
             └────────┬─────────┘
                      │  seed concepts
             ┌────────▼─────────┐
             │   GraphExpander   │  multi-hop weighted BFS over the concept graph
             └────────┬─────────┘
                      │  expanded concepts (+ paths, hops, scores)
             ┌────────▼─────────┐
             │   GraphRetriever  │  per-resource graph score → graph-aware re-rank
             └────────┬─────────┘
                      │
      graph evidence (concept paths)  +  chunk evidence (citations preserved)
```

Package: [`src/ala/retrieval/graphsearch/`](../src/ala/retrieval/graphsearch/) —
`config` · `models` · `linker` · `expander` · `retriever` · `factory` ·
`benchmark` · `viz`.

## Pipeline

1. **Seed** — `HybridRetriever.retrieve(query, top_k=candidate_k)` returns the
   candidate chunks (dense + BM25 + RRF); their resources become graph entry
   points.
2. **Link** (`QueryConceptLinker`) — concepts are linked two ways: **direct
   alias match** on the query (longest-alias-first, acronym-aware, so
   "convolutional neural network" beats "neural network") and **seed-resource
   concepts** (concepts attached to the resources hybrid already surfaced).
3. **Expand** (`GraphExpander`) — best-first BFS over concept↔concept edges
   (`related_to`, `prerequisite`, `depends_on`, `extends`). A neighbour's score
   = `parent × edge_weight × hop_decay`; the higher score wins and the reaching
   **path** is recorded. Bounded by `max_hops` (depth), `beam` (frontier width),
   `max_expanded` (total).
4. **Score resources** — each expanded concept contributes its score to the
   resources it points to via `appears_in` / `mentioned_in` / `explains` /
   `example_of` (provenance edges). `resource_graph_score[r] = max` concept score.
5. **Graph-aware re-rank** — every hybrid candidate keeps its fused score and
   gains `graph_weight × normalised resource_graph_score`. Chunks whose resource
   is reachable from the query's concepts rise. `component_scores['graph']` is
   recorded; citations are untouched.
6. **Return** — graph-aware **chunk evidence** *and* **graph evidence** (the
   concept paths, as `GraphEvidenceItem`s that plug straight into the Evidence
   Package `graph_evidence` field).

## Algorithms

- **Relationship-aware traversal** — edge weights (`config.edge_weights`) make a
  `prerequisite`/`explains` hop worth more than a loose `related_to`
  co-occurrence hop; `strategy: bfs` ignores weights (pure hop-decay).
- **Path & confidence scoring** — every expanded concept stores `hop`,
  `relationship` (the edge type that reached it) and the full concept `path`;
  graph-evidence `confidence` is the concept node's own calibrated confidence.
- **Graph filtering** — `min_edge_weight` drops weak edges; `allowed_edge_types`
  restricts which relations are walked.
- **Traversal-depth control** — `max_hops` (1/2/3) with a decay so deep, weak
  concepts cannot overrule strong shallow ones.

Relationships understood: `prerequisite`, `depends_on`, `explains`,
`related_to`, `example_of`, `appears_in`, `mentioned_in`, `contains`
(`prerequisite`/`depends_on` currently exist between modules and as provenance;
concept↔concept expansion is dominated by `related_to` until G2 adds semantic
edges — see Limitations).

## CLI

```powershell
ala graph-retrieve "convolutional neural network"     # chunks + graph evidence
ala graph-retrieve "gradient descent" --hops 3 --top-k 8
ala graph-retrieve --benchmark --n 100                # eval + 11 figures
```

## Configuration (`config/platform.yaml → graph.retrieval`)

`max_hops` · `hop_decay` · `graph_weight` · `candidate_k` · `top_concepts` ·
`beam` · `max_expanded` · `max_graph_evidence` · `strategy` · `min_edge_weight`
· `edge_weights`. All have safe defaults (`GraphRetrievalConfig`).

## Benchmark (real corpus, 100 queries — no mocks)

Reuses the label-free known-item eval set (Stage 8).
`reports/stage11_graph_retrieval/`.

**Ranking — related-passage (semantic):**

| retriever | Hit@1 | Hit@5 | MRR | nDCG@10 | latency |
|---|---|---|---|---|---|
| Hybrid | 0.710 | 0.880 | 0.778 | 0.653 | 113 ms |
| **Graph** | 0.710 | **0.890** | **0.782** | **0.669** | 116 ms |

Graph-aware re-ranking gives a **small, real** gain on the semantic task
(nDCG +0.016, Hit@5 +0.01, MRR +0.004) at ~2 % latency cost; known-item is
unchanged (0.90 Hit@1) — the gold resource is already hybrid's top result.

**Graph metrics:** concept-link coverage 1.00 · graph recall 1.00 · concept
coverage 0.97 · node 0.21 · edge 0.31 · graph-evidence→gold 0.30 · 116 ms · 8.6
qps.

**Traversal-depth ablation:** Hit@1 / MRR / nDCG are identical at 1/2/3 hops —
see Limitations.

## Visualizations (`figures/`, presentation-ready)

`ranking_comparison` · `graph_coverage` · `hop_distribution` ·
`traversal_depth_comparison` · `latency` · `node_importance` ·
`edge_importance` · `evidence_composition` · `traversal_example` ·
`retrieved_graph` · `concept_expansion`.

## Tests

[`tests/test_graph_retrieval.py`](../tests/test_graph_retrieval.py) — linker
(alias + seed-resource), expander (multi-hop paths, depth control, weighted edge
scoring), retriever (graph-aware ranking promotes reachable resources, graph
evidence, citation preservation), Evidence-Package round-trip, and a real-corpus
integration test. 9 tests; full suite **142 passed**.

## Examples

`"convolutional neural network"` → seeds {CNN, Neural Network, Deep Learning,
Activation Function, Optimizer, Image Classification, …}; 1-hop expansion adds
Overfitting, Regularization, Transfer Learning, Fine-Tuning, Loss Function,
Dropout; the graph boost lifts `applied-dl` CNN lab/lecture chunks to the top.
See `figures/traversal_example.png`.

## Limitations (honest)

- **Multi-hop doesn't move the ranking metrics** on this corpus: `graph_recall`
  saturates at **hop 0** (seed concepts already come from the seed resources, so
  the gold resource is reachable immediately), and deeper concepts carry
  decayed scores that cannot overturn the top ranking. The ablation is therefore
  flat. Multi-hop's value is in **graph evidence / reasoning breadth** (used by
  GraphRAG at Stage 12) and in **multi-hop questions** whose answer spans
  concepts not co-located in one resource — that is measured properly in Stage
  13, not here.
- Concept↔concept expansion is driven by `related_to` (co-occurrence);
  confidence-scored semantic `prerequisite`/`explains` edges between concepts
  need the LLM (G2) and arrive with Stage 12.
- The graph arm **re-ranks** the hybrid candidate pool; it does not yet pull in
  entirely new chunks from graph-reached resources absent from the pool (a
  recall extension left as a clean hook on `GraphRetriever`).

## Extension hooks (designed, not implemented)

`GraphRetriever` is the seam for later features: **Research Mode** (deeper
`max_hops` + path export), **Citation Explorer** (the `path`/provenance already
on every `GraphEvidenceItem`), **Student Model** (concept scores → mastery),
**Web-Search Fallback** (a second `Retriever` fused the same way). GraphRAG
(Stage 12) consumes `retrieve_with_graph()` directly.
