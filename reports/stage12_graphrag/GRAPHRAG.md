# Stage 12 — GraphRAG: Benchmark

Real corpus, **60 questions**, offline extractive-grounded generator.

## Metrics

| metric | value |
|---|---|
| grounding ratio | 1.0 |
| citation validity | 1.0 |
| answer has citation | 1.0 |
| context precision | 0.6131 |
| context recall | 1.0 |
| graph coverage (≥1 concept) | 1.0 |
| avg concepts / context | 8.0 |
| multi-hop presence (≥1 relation) | 1.0 |
| avg relations / context | 2.0 |
| avg context tokens | 330.15 |
| mean latency (ms) | 79.7142 |
| throughput (qps) | 12.54 |
| citation source types | {'pdf': 107, 'notebook': 5, 'slide': 6} |

## Example — "what is a convolutional neural network"

**Answer:** Key concepts: Convolutional Neural Network [K1], Feature Engineering [K2], Overfitting [K3]. [C1] We built our first Convolutional Neural Network (CNN). [C2] Convolutional Neural Network Model. [C3] Lab 5 Building Your First Convolutional Neural Network (CNN) Instructor: [Instructor's Name] Date: [Date] Applied Deep Learning Today's Lab Agenda 1.

grounding=1.0 · valid=True · confidence=0.8815 · generator=extractive-grounded

| citation | source | type | confidence |
|---|---|---|---|
| K1 | Convolutional Neural Network | concept | 1.0 |
| K2 | Feature Engineering | concept | 1.0 |
| K3 | Overfitting | concept | 1.0 |
| C1 | [practical-dl-lec6-1, p.1-20] | pdf | 0.9485 |
| C2 | [multiclass-classification-with-convolutional-neural-networks, Convolutional Neural Network Model] | notebook | 0.8773 |
| C3 | [practical-dl-lab5, p.1-5] | pdf | 0.7527 |

**Reasoning trace:**
- Retrieved 8 candidate passages (hybrid + graph-aware ranking).
- Linked the question to 8 seed concept(s); expanded to 60 concept(s) over 1 hop(s).
- Graph reached 147 resource(s) through concept edges.
- Assembled a 617-token grounded context: 5 source(s) + 8 concept(s).

## Figures (`figures/`)
- `pipeline_diagram.png` · `grounding.png` · `context_composition.png`
- `citation_sources.png` · `token_distribution.png` · `context_precision_recall.png`
- `evidence_contribution.png` · `reasoning_flow.png`

## Honest note
The offline generator is **extractive-grounded** (selects + cites real passages), so grounding/citation-validity are ~1.0 by construction — this measures the *pipeline's* grounding guarantee, not an LLM's. Fluent NL synthesis + faithfulness under an actual LLM is evaluated at Stage 13 via the `OpenAICompatibleLLM` seam.
