# Stage 19 — Learning Analytics Dashboard

Demo learner (scripted events; all analytics are real computations over the real concept graph + catalog).

## Summary
- overall mastery **0.4234** · tracked 8 · weak 4 · strong 4 · events 39
- estimated time spent **210 min** {'quiz': 72.0, 'reading': 32.0, 'lesson': 60.0, 'video': 40.0, 'interaction': 6.0}
- completion: concept coverage 0.0611 · 11 resources completed

## Mastery by domain

| domain | mastery | concepts |
|---|---|---|
| mined | 0.125 | 1 |
| statistics | 0.134 | 2 |
| deep-learning | 0.521 | 3 |
| data-mining | 0.715 | 1 |
| machine-learning | 0.715 | 1 |

## Recommendations (engine)

| kind | concept | reason |
|---|---|---|
| review | Structure Sentence | mastery 0.13 is below target |
| review | Probability Distribution | mastery 0.13 is below target |
| review | Optimizer | mastery 0.13 is below target |
| review | Random Variable | mastery 0.13 is below target |
| explore | SQL Join | builds on your strong Clustering |
| explore | Data Preprocessing | builds on your strong Activation Function |
| explore | Regression Analysis | builds on your strong Deep Learning |

## Deliverables
- **`dashboard.html`** — self-contained interactive dashboard (tabs: Overview / Mastery / Progress / Recommendations; hover tooltips on every chart).
- Figures (`figures/`): `mastery_by_domain` · `mastery_heatmap` · `confidence_evolution` · `completion_and_time` · `recommendations`.

## Honest notes
- The learner event stream is synthetic (no real users); every analytic — mastery, domain roll-up, heatmap, completion, time-spent, confidence, recommendations — is a real computation over the real concept graph + catalog.
- Time-spent is **estimated** from event type × typical duration (configurable), not measured wall-clock (no session timing is collected yet).
