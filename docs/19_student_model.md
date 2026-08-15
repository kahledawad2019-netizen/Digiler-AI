# Stage 18 — Student Model

A persistent learner profile stored **separately** from the Knowledge Base (its own
SQLite db). It tracks preferences, learning level/pace/goals, longitudinal history
(lessons, quizzes, videos, reading, exams) and **per-concept mastery** keyed to the
concept-graph ids — and the retriever personalises toward the learner's weak
concepts. Fully **additive**: `PersonalizedRetriever` wraps the existing retriever;
mastery keys into the existing concept graph. Package:
[`src/ala/student/`](../src/ala/student/).

## Separation from the KB

The learner's data lives in `data/student/student.db` (three tables: `students`,
`concept_mastery`, `events`). The knowledge catalog is never touched — V3's rule
that *student state is not resource state*. Concept mastery references concept-graph
ids, so the two connect without coupling.

## Architecture

```
learning events (quiz/exam/lesson/video/reading/interaction)
        │  MasteryModel (difficulty-scaled EMA)
        ▼
   per-concept mastery [0,1]  →  weak / strong concepts
        │                              │  (weak concept → resources via graph)
        ▼                              ▼
   analytics (dashboards)      PersonalizedRetriever  → remediation-aware ranking
                                       │
                                       ▼  same GraphRAG / Evidence / Citation stack
```

## Components

- **StudentStore** ([store.py](../src/ala/student/store.py)) — SQLite persistence,
  separate db.
- **MasteryModel** ([mastery.py](../src/ala/student/mastery.py)) — bounded [0,1]
  mastery updated toward the outcome at a difficulty-scaled rate (Elo-flavoured EMA);
  assessment events (quiz/exam) carry full signal, exposure events nudge gently.
- **StudentModel** ([model.py](../src/ala/student/model.py)) — record events, query
  weak/strong concepts, mastery summary, profile CRUD.
- **PersonalizedRetriever** ([personalize.py](../src/ala/student/personalize.py)) —
  wraps any `Retriever`; boosts resources teaching the learner's weak concepts (via
  the graph) + preference (language / explanation-style → doc type). Records
  `component_scores['student']`.
- **Analytics** ([analytics.py](../src/ala/student/analytics.py)) — mastery
  distribution, weak/strong, timeline, confidence history, progress.

Tracked profile fields: level · preferred language · explanation style · difficulty
preference · learning pace · goals · completed lessons/quizzes/videos/reading · exam
history · confidence history · **concept mastery** + overall mastery score.

## CLI

```powershell
ala student --student ada --quiz incorrect --concept concept:gradient-descent
ala student --student ada                 # show mastery summary + weakest concepts
ala student --benchmark
```

## Configuration (`config/platform.yaml → student`)

`location` · `mastery_k` · `weak_threshold` · `strong_threshold` ·
`personalization.{weak_weight, pref_weight, candidate_k}`.

## Benchmark (real graph + retriever, isolated profile — no mocks)

`reports/stage18_student/`. A demo learner with a *scripted* event stream drives the
**real** mastery model and personaliser over the real concept graph + hybrid
retriever.

| result | value |
|---|---|
| seeded-weak correctly classified weak | **1.00** |
| seeded-strong correctly classified strong | **1.00** |
| learning curve (quiz seq 0,0,0,1,0,1,1,1,1) | 0.30 → 0.11 → **0.80** |
| weak-concept resources (via graph) | 88 |
| base weak-coverage@10 | 0.65 |
| **personalized** weak-coverage@10 | **1.00** (lift **+0.35**) |

Mastery cleanly separates weak/strong; the learning curve crosses the weak (0.4) and
strong (0.7) thresholds as expected; personalisation lifts weak-concept coverage.

## Visualizations (`figures/`)

`student_pipeline` · `mastery_distribution` · `weak_strong_concepts` ·
`learning_curve` · `personalization_effect`.

## Tests

[`tests/test_student.py`](../tests/test_student.py) — store round-trip, mastery
up/down + exposure + thresholds, record-quiz → weak/strong, **PersonalizedRetriever
promotes a weak-concept resource**, and analytics shape. Full suite **194 passed**.

## Limitations (honest)

- The learner event stream in the benchmark is **synthetic** (no real users); every
  mastery update, weak/strong classification and retrieval personalisation is a real
  computation over the real graph + retriever.
- The personalisation lift (0.65 → 1.00) is large partly because the demo's weak
  concepts are *broad* (Probability Distribution, Optimizer, Random Variable) with 88
  backing resources; narrower weak concepts yield smaller, still-positive lifts.
- Mastery is a transparent EMA, not a fitted IRT/BKT model — deliberately simple and
  inspectable; a Bayesian-Knowledge-Tracing upgrade is a clean drop-in behind
  `MasteryModel`.

## Extension hooks

- **Analytics Dashboard (19):** `compute_analytics()` is the data source.
- **Study Planner (20):** weak concepts + goals + pace → a schedule.
- **RL Adaptive (21):** mastery + response history is the observation; the reward
  updates the same profile.
- **GraphRAG personalisation:** `PersonalizedRetriever` drops into `GraphRAGService`
  as the base retriever for personalised, cited answers.
