# Stage 20 — Study Planner: Benchmark

Goal: **master my weak concepts before the final exam** · deadline 10 days · 60 min/day.

## Plan quality

| metric | value |
|---|---|
| days used / deadline | 7 / 10 |
| fits deadline | **True** |
| max day load (≤ budget) | **59** / 60 min |
| total study time | 321 min |
| activities | 21 {'read': 6, 'quiz': 6, 'practice': 3, 'revision': 6} |
| concepts / weak | 6 / 6 |
| time on weak concepts | **100%** |
| prerequisite (week) ordered | **True** |
| unscheduled (over budget) | 0 |

## Concept order (prerequisite week → weakest first)

| concept | mastery | curriculum week |
|---|---|---|
| Optimizer | 0.114 | week 1 |
| Probability Distribution | 0.114 | week 2 |
| Activation Function | 0.114 | week 2 |
| Random Variable | 0.114 | week 4 |
| Clustering | 0.114 | week 6 |
| Structure Sentence | 0.114 | week - |

## Deliverables
- **`study_plan.html`** — self-contained visual study-plan timeline.
- Figures (`figures/`): `study_timeline` · `time_allocation` · `daily_load`.

## Honest notes
- The learner is a scripted demo (no real users); the plan, ordering, time budgeting and revision spacing are real computations over the real concept graph.
- Prerequisite ordering uses the **curriculum week** of each concept's resources (a real signal); concept-to-concept prerequisite edges (G2) would refine it further.
- Activity durations come from config (`planner.activity_minutes`) scaled by concept difficulty; a single core activity may exceed the daily budget on an otherwise empty day.
