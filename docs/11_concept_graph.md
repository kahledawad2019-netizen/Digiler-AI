# Stage 10 — Concept Graph Construction

A lightweight **educational** knowledge graph (explicitly **not** Microsoft
GraphRAG, per V3 §4). SQLite persistence + NetworkX in-memory. Built
deterministically (no LLM) from the ingested corpus; every node/edge keeps
provenance to resource ids.

## Node & edge types

**Nodes** (`NodeType`): `course`, `module`, `resource`, `topic`, `concept`,
`chunk`. Requested types map here (V3 §4.2 — a *scoped* concept graph, not an
everything-graph): lessons/documents/videos → **resource** (by `doc_type`),
subtopics → **topic**; definitions/examples/exercises/assignments are captured
via `example_of` edges + role tags rather than a node explosion.

**Edges** (`EdgeType`): `contains`, `appears_in`, `mentioned_in`, `explains`,
`related_to`, `prerequisite`, `depends_on`, `example_of`, `references`, `extends`.

## Build algorithm (deterministic, G1)
1. **Structural hierarchy** from the catalog + taxonomy: `course ⊃ module ⊃
   resource ⊃ topic` via `contains`.
2. **Concepts** = curated seed (`concepts.seed.yaml`, multilingual EN/AR) +
   **frequency-mined** resource keywords (a keyword spanning ≥ `min_concept_resources`
   resources becomes a concept, capped per course).
3. **Concept ↔ content**: `appears_in` (concept in a resource's title/topics),
   `mentioned_in` (keyword-only), `explains` (concept in the title), `example_of`
   (assessment/example resources).
4. **Concept ↔ concept**: `related_to` by **co-occurrence** (weighted, pruned).
5. **Prerequisites**: `module wN → wN+1` prerequisite/`depends_on` chains per
   course; `references`/`extends` from `ResourceMetadata.relationships`.

## Persistence & CLI
SQLite at `data/graph/concept_graph.db` (`nodes`, `edges` tables). NetworkX
`MultiDiGraph` in memory for traversal/statistics.
```powershell
ala graph build     # build + persist + print statistics
ala graph report    # + figures + reports/stage10_graph/
ala graph stats
ala graph show --concept probability     # navigate a concept's neighbourhood
```

## Statistics (real corpus, after concept upgrade)
- **1,511 nodes** — course 7 · module 70 · resource 257 · topic 1,046 · concept 131.
- **4,779 edges** — contains / related_to / mentioned_in / appears_in / explains /
  prerequisite / depends_on.
- density 0.0021 · avg degree 6.33 · **1 weakly-connected component** (cleaner
  concepts bridge the domains — was 3 before the upgrade).
- top concepts by frequency: Probability Distribution, Optimizer, Machine
  Learning, Neural Network, Gradient Descent, Regularization.

## Visualizations (`reports/stage10_graph/figures/`)
- `graph_statistics.png` — nodes/edges by type.
- `concept_network.png` — top concepts + `related_to` (clear domain clusters: ML
  centre, statistics, English/NLP, Excel).
- `prerequisite_chains.png` — module learning paths per course.

## Validation
`tests/test_graph.py`: add/dedupe/statistics, SQLite save/load round-trip (with
provenance), and `build_from_metas` (structural hierarchy + module prerequisites
+ concept linking).

## Concept-extraction quality upgrade (Stage 10.5)
The first build used raw frequency keyword mining → generic concepts (data,
example, model, plt). This was replaced by `ala.graph.concepts.ConceptExtractor`
(graph schema unchanged — richer fields live in the concept node's `attrs`):
- **Curated domain lexicon** (`config/taxonomy/concept_lexicon.yaml`, ~80 concepts
  across DB/SQL, statistics, ML, DL, LLM/agentic, CV, data-analysis) matched over
  the **full chunk text** (not just top-12 keywords), acronym-aware
  (CNN→Convolutional Neural Network, FK→Foreign Key).
- **Embedding-aware multi-word mining** (KeyBERT-style): 2–4-gram candidates,
  domain-stopword + generic filtering, kept only if e5-similar to the lexicon.
- Each concept now carries **canonical name, aliases, confidence, frequency,
  source resources, provenance**.

**Result:** concepts **247 → 131** (71 lexicon + 60 mined, 122 multi-word);
generic terms removed; top concepts are now Probability Distribution (427),
Optimizer (305), Machine Learning (188), Neural Network (147), Gradient Descent
(137). `Foreign Key` is now correctly linked (was isolated). Report:
`reports/stage10_graph/CONCEPT_QUALITY.md` + `concept_quality.json` +
before/after figures. CLI: `ala graph concepts --model e5-small`.

## Honest limitations
- The 60 **mined** concepts (domain-tagged `mined`) are embedding-filtered
  multi-word phrases — a few are still coarse; the lexicon concepts are clean.
  Tightening is a lexicon-expansion + threshold task, no code change.
- **Typed relations** (`prerequisite`/`explains`) between *concepts* are still
  structural (co-occurrence, module order). G2 LLM relation extraction (needs the
  LLM at Stage 12) would add confidence-scored semantic edges.
- Chunk-level nodes are edge provenance (resource ids), not 21k separate nodes,
  keeping the graph tractable/visualizable (V3 anti-everything-graph).

## Integration
`ConceptGraph.neighbors()` (typed, directional, with provenance) is the traversal
primitive **Stage 11 (Graph Retrieval)** uses for neighbour/concept expansion and
multi-hop; graph evidence will join chunk evidence in the same Evidence Package
(Stage 12). The concept ontology keys the future Student-Model mastery table.
