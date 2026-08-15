# Stage 12 — GraphRAG

The generation layer (V3 §5) on top of the retrieval engine. It turns a question
into a **grounded, cited answer**, reusing every previous stage and adding only
the context/prompt/generation machinery. Fully **additive** — the retrieval,
graph, and evidence modules are untouched.

## Architecture

```
question
   │
   ▼  GraphEvidenceMerger  ── runs GraphRetriever once ──────────────┐
   │     graph-aware chunk evidence  +  concept-path graph evidence   │
   ▼  → EvidenceBuilder.build_from_results  → EvidencePackage         │  (LLM never
   │        (items + graph_evidence, citations, confidence)           │   sees any
   ▼  GraphContextBuilder                                             │   of this)
   │     dedupe · token-budget · compress · order · derive relations, │
   │     prerequisites, neighbour concepts → ReasoningContext         │
   ▼  GraphPromptBuilder  → grounded prompt  ────────────────────────┘
   │
   ▼  generator (ExtractiveGrounded default | LLMBacked)  → answer text
   │
   ▼  GraphCitationManager  → grounding check + used citations
   │
   ▼  GraphRAGAnswer  (answer · citations · reasoning trace · grounding · confidence)
```

Package: [`src/ala/rag/`](../src/ala/rag/) — `models` · `merger` · `context` ·
`prompt` · `citations` · `llm` · `pipeline` · `benchmark` · `viz`.

## The four requested components

- **GraphEvidenceMerger** ([merger.py](../src/ala/rag/merger.py)) — runs the graph
  retriever once and folds its two outputs (graph-aware chunks + concept-path
  evidence) into one `EvidencePackage` via the existing `EvidenceBuilder`
  (`build_from_results`, added additively — no retrieval/item logic duplicated).
- **GraphContextBuilder** ([context.py](../src/ala/rag/context.py)) — builds the
  `ReasoningContext`: duplicate removal (`resource+heading`), **context budgeting**
  (token-bounded), **compression** (per-chunk truncation), **ordering** (by
  confidence), and the graph scaffold — concepts, relations, prerequisites,
  neighbour concepts (deliberately reserves ~⅓ of concept slots for hop≥1
  neighbours so multi-hop relations are present to reason over).
- **GraphPromptBuilder** ([prompt.py](../src/ala/rag/prompt.py)) — renders the
  context into a graph-aware, grounded prompt: concept scaffold + relations +
  prerequisites + numbered `[C#]` source evidence, with a system rule to answer
  **only** from the evidence and cite every claim.
- **GraphCitationManager** ([citations.py](../src/ala/rag/citations.py)) — assigns
  `[C#]` (chunks) / `[K#]` (concepts), keeps a resolvable index (resource,
  page/slide/timestamp, confidence) for the Citation Explorer (Stage 15), and
  **checks grounding**: a sentence is grounded iff it carries a valid citation;
  invalid citations are flagged.

## Context contents (all present)

chunks · concepts · relations · graph paths · prerequisites · neighbour concepts
· citation metadata · page / slide / video-timestamp · confidence · reasoning
trace — see `ReasoningContext` in [models.py](../src/ala/rag/models.py).

## Grounding guarantee

The LLM **only** receives the structured prompt — raw retrieval never reaches it.
The default **`ExtractiveGroundedGenerator`** composes the answer strictly from
context evidence sentences, each emitted with a **leading citation**, so it is
grounded *by construction* (cannot hallucinate). This is a real strategy — the
generation-layer analogue of the dependency-free `HashingEmbedder` — not a mock.
A real LLM is a drop-in via **`LLMBackedGenerator` + `OpenAICompatibleLLM`**
(stdlib HTTP, configured by `graphrag.llm` or `ALA_LLM_*` env), for a local
Qwen2.5 / vLLM server.

## CLI

```powershell
ala graphrag "what is a convolutional neural network and why use pooling"
ala graphrag "explain gradient descent" --top-k 8 --json
ala graphrag --benchmark --n 60          # metrics + 8 figures
```

## Configuration (`config/platform.yaml → graphrag`)

`top_k_chunks` · `context_chunks` · `context_concepts` · `token_budget` ·
`max_chunk_tokens` · `dedupe_by` · `min_confidence` · `llm.{base_url,model,api_key,temperature}`.

## Benchmark (real corpus, 60 questions — no mocks)

`reports/stage12_graphrag/`.

| metric | value |
|---|---|
| grounding ratio | **1.00** |
| citation validity | **1.00** |
| answer has citation | 1.00 |
| context precision | 0.61 |
| context recall | **1.00** |
| graph coverage (≥1 concept) | 1.00 |
| multi-hop presence (≥1 relation) | **1.00** (avg 2.0 relations) |
| avg context tokens | 330 |
| mean latency | 80 ms (**12.5 qps**) |
| citation sources | pdf 107 · slide 6 · notebook 5 |

The extractive-grounded generator gives grounding/citation-validity **1.0 by
construction** — this validates the *pipeline's* grounding guarantee, not an
LLM's fluency. Context recall 1.0 / precision 0.61 show the right resource is
always in context with reasonable focus.

## Visualizations (`figures/`, presentation-ready)

`pipeline_diagram` · `grounding` · `context_precision_recall` · `citation_sources`
· `token_distribution` (context compression) · `context_composition` ·
`evidence_contribution` · `reasoning_flow`.

## Tests

[`tests/test_graphrag.py`](../tests/test_graphrag.py) — context builder (dedupe /
budget / graph scaffold), prompt builder, citation & grounding (valid vs invalid),
extractive generator (grounded, empty-context), evidence merger, end-to-end
grounded answer, citation-provenance preservation, and a real-corpus integration
test. 10 tests; full suite **152 passed**.

## Example

`"what is a convolutional neural network"` → *"Key concepts: Convolutional Neural
Network [K1], Feature Engineering [K2], Overfitting [K3]. [C1] We built our first
Convolutional Neural Network (CNN). [C2] Convolutional Neural Network Model. …"* —
grounding 1.0, citations resolve to `applied-dl` lab/lecture pages.

## Limitations (honest)

- The offline generator is **extractive** — it selects and cites real passages
  but does not synthesise fluent prose; grounding is therefore trivially 1.0.
  Fluent answers + faithfulness under a real model need the `OpenAICompatibleLLM`
  seam and are evaluated at **Stage 13**.
- Concept↔concept **relations** shown in context are `related_to` (co-occurrence);
  semantic `prerequisite`/`explains` relations between concepts await G2 LLM
  relation extraction.
- Context precision (0.61) reflects that the top-k pool mixes the gold resource
  with topically-adjacent ones — expected for a dense technical corpus.

## Extension hooks (designed, not implemented)

`GraphRAGService` / `GraphRAGAnswer` are the seams for later stages: **Research
Mode** (Stage 14 — a confidence gate on `ans.confidence` + a second retriever
fused by the merger), **Citation Explorer** (Stage 15 — the `CitationRecord`
index already carries page/slide/timestamp), **Student Model** (Stage 18 —
`graph_evidence` concept ids → mastery), **AI Agents** (Stage 22 — the pipeline
is a tool a Tutor/Retriever agent calls). The `LLMClient` protocol is the seam
for any generator backend.
