# Stage 18 — Student Model: Benchmark

Demo learner (scripted events; all mastery + personalisation are real computations).

Seeded weak: Probability Distribution, Optimizer, Random Variable · strong: Structure Sentence, Clustering, Activation Function.

## Mastery model

| metric | value |
|---|---|
| overall mastery | 0.4339 |
| concepts tracked | 6 |
| weak / strong | 3 / 3 |
| events recorded | 27 ({'quiz': 18, 'reading': 3, 'lesson': 3, 'video': 3}) |
| seeded-weak correctly classified weak | **1.0** |
| seeded-strong correctly classified strong | **1.0** |

## Learning curve (one concept, quiz sequence [0, 0, 0, 1, 0, 1, 1, 1, 1])
mastery: [0.3, 0.217, 0.158, 0.114, 0.358, 0.259, 0.463, 0.611, 0.718, 0.795]

## Personalised retrieval (weak-concept remediation, real hybrid retriever)

| metric | value |
|---|---|
| weak-concept resources | 88 |
| base weak-coverage@10 | 0.65 |
| **personalized** weak-coverage@10 | **1.0** |
| lift | **+0.35** |

## Weakest concepts

| concept | mastery | attempts |
|---|---|---|
| Probability Distribution | 0.125 | 4 |
| Optimizer | 0.125 | 4 |
| Random Variable | 0.125 | 4 |

## Figures (`figures/`)
`student_pipeline` · `mastery_distribution` · `weak_strong_concepts` · `learning_curve` · `personalization_effect`.

## Honest notes
- Storage is a **separate** SQLite db (never the KB catalog). The learner's event stream is synthetic (no real users); the mastery updates, weak/strong classification and retrieval personalisation are real executions over the real concept graph + hybrid retriever.
- Personalisation boosts resources that teach the learner's weak concepts; the lift depends on how much the base ranking already covers them.
