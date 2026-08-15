# Stage 22 — AI Agents: Benchmark

**7 agents** (Tutor / Quiz / Evaluator / Planner / Research / WebResearch / KnowledgeCurator) + Coordinator, dependency-free framework. Every agent reuses the shared services — **one retrieval path** (GraphRAG), no duplication.

## Coordinator routing
- accuracy **1.0** over 12 labelled requests.

## Tutor (grounded via GraphRAG)
- mean grounding **1.0** · mean latency 224.7 ms.

## Quiz → Evaluator loop
- 8 concepts · good-answer accuracy **1.0** · bad-answer rejection **1.0** · discrimination **1.0**.

## End-to-end study session (Tutor → Quiz → Evaluator → Planner)
- 3 sessions, all completed: **True**. Example (`concept:probability-distribution`):

| agent | output |
|---|---|
| Tutor | (concise explanation) Key concepts: Probability Distribution [K1], Reg |
| Quiz | [very-easy] Define the concept of 'concept:probability-distribution'. |
| Evaluator | Correct — you covered the key ideas (binomial, distribu-, frequently,  |
| Planner | Study plan: 11 days, 589 min total. |

- outcome correct: **True** · mastery after: 0.4225

## Figures (`figures/`)
`architecture` · `routing_accuracy` · `quiz_evaluation` · `agent_latency`.

## Honest notes
- Coordinator routing is deterministic keyword intent (no LLM); an LLM router is a clean upgrade behind the same interface.
- Quiz generation + grading are **extractive** (question + key from real evidence, grading by key-term recall) — grounded, no hallucination; an LLM would add fluency.
- CrewAI is an optional seam (`agents.framework: crewai`); the native framework needs no external dependency and reuses the exact same tools/services.
