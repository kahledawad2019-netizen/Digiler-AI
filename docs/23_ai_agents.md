# Stage 22 — AI Agents

A multi-agent layer where each agent is a **role over the existing services** —
never a new retrieval, ingestion or scoring path. A Coordinator routes a request to
the right agent; a Crew runs collaborative flows. Fully **additive**; the framework
is dependency-free (CrewAI is an optional seam). Package:
[`src/ala/agents/`](../src/ala/agents/).

## The roster (7 agents + Coordinator)

| agent | reuses | does |
|---|---|---|
| **Tutor** | GraphRAG (+RL style) | grounded, cited explanations, personalised style |
| **Quiz** | GraphRAG evidence + RL | an adaptive quiz question at the learner's difficulty |
| **Evaluator** | grader + Student Model + RL | grades the answer, advances mastery, updates the policy |
| **Planner** | Study Planner | an adaptive study plan |
| **Research** | Research Mode | confidence-gated KB / web answer |
| **WebResearch** | Web Search | ranked web sources |
| **KnowledgeCurator** | Incremental Ingestor | grows the Knowledge Base |
| **Coordinator** | — | intent routing + crew orchestration |

## One retrieval path (no duplication)

Every retrieving agent calls the **`retrieval_qa` / `evidence` tool**, which wraps a
**single shared `GraphRAGService`**; Research Mode reuses that same GraphRAG handle.
The Tool registry ([tools.py](../src/ala/agents/tools.py)) is the one place any
capability is exposed — the same registry powers Function Calling (Stage 23).

```
                Coordinator (intent routing)
                     │
   Tutor · Quiz · Evaluator · Planner · Research · WebResearch · Curator
                     │  tools  (single source of truth per capability)
   GraphRAG · Student Model · RL Policy · Study Planner · Research Mode · Ingestor
```

## Crew flow (collaboration)

`study_session(student, concept)`: **Tutor** explains → **Quiz** asks an adaptive
question → **Evaluator** grades it (advancing mastery + the RL policy) → **Planner**
recommends next — all sharing the same services.

## CLI

```powershell
ala agents "explain convolutional neural networks"        # routed to the Tutor
ala agents "quiz me on gradient descent" --student ada
ala agents --session "Gradient Descent" --student ada     # full study session
ala agents --benchmark
```

## Configuration (`config/platform.yaml → agents`)

`framework` (`native` | `crewai`) · `grade_threshold`.

## Benchmark (real corpus — no mocks) — `reports/stage22_agents/`

| metric | value |
|---|---|
| agents | 7 (+ Coordinator) |
| coordinator routing accuracy | **1.00** (12 requests) |
| Tutor grounding (GraphRAG) | **1.00** · 225 ms |
| Quiz → Evaluator good-answer accuracy | **1.00** |
| Quiz → Evaluator bad-answer rejection | **1.00** |
| grading discrimination | **1.00** (8 concepts) |
| study sessions completed | 3/3 |
| **retrieval paths** | **1** (shared GraphRAG) |

## Visualizations

`architecture` (hub-and-spoke: Coordinator → agents → shared services) ·
`routing_accuracy` · `quiz_evaluation` · `agent_latency`.

## Tests

[`tests/test_agents.py`](../tests/test_agents.py) — routing intents, quiz
generation + grading, Tool run, Tutor (retrieval-only), Quiz→Evaluator records
mastery, crew study session, and a real-corpus integration test. Full suite
**216 passed**.

## Limitations (honest)

- Coordinator routing is **deterministic keyword intent** (no LLM); an LLM router is
  a clean upgrade behind the same interface.
- Quiz generation + grading are **extractive** (question + key from real evidence;
  grading by key-term recall) — grounded, no hallucination, but an LLM would add
  fluency and free-text nuance. The 1.00 discrimination reflects an easy good/bad
  split (exact key vs unrelated); real learner answers are subtler.
- **CrewAI** is an optional seam (`agents.framework: crewai`) — not installed here;
  the native framework reuses the exact same tools/services with no dependency.

## Extension hooks

- **Function Calling (Stage 23):** the `Tool` registry is already the callable
  surface — a router (LLM or rules) dispatches tool calls through the same objects.
- **New agents** (Flashcard, Coach) drop in by composing existing tools.
- **LLM upgrade:** swap the extractive generator for `OpenAICompatibleLLM` (Stage 12
  seam) and the agents produce fluent NL with the same grounding guarantees.
