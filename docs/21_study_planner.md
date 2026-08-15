# Stage 20 — Study Session Planner

Given a **goal**, a **deadline**, **available daily time** and the learner's
**Student Model**, produces an adaptive daily study plan (read / watch / practice /
quiz / revision) with a visual timeline. Fully **additive** — reads the Student
Model + concept graph; changes none. Package: [`src/ala/planner/`](../src/ala/planner/).

## Algorithm

1. **Select concepts** — explicit `concept_ids`, a whole `course`, or (default) the
   learner's **weak concepts**; cold-start falls back to top concepts by frequency.
2. **Order** — by **curriculum week** (prerequisite: earlier-week concepts first)
   then **weakness** (lowest mastery first).
3. **Activities per concept** — read (lesson/slides/textbook), watch (video),
   quiz (always); **weak** concepts also get **practice** + **spaced revision**.
   Durations come from config, **scaled by difficulty** (weaker → longer).
4. **Schedule** — greedily pack activities into days within `minutes_per_day` and
   the deadline; insert each concept's revision `revision_gap_days` later (spaced
   repetition), finding the next day with room.
5. **Report** — a `StudyPlan` of `StudyDay`s + stats (fit, budget, weak share,
   unscheduled).

## Components

- **StudyPlanner** ([scheduler.py](../src/ala/planner/scheduler.py)) — selection,
  ordering, activity generation, time-budgeted scheduling, spaced revision.
- **models** — `StudyGoal`, `StudyActivity`, `StudyDay`, `StudyPlan`.
- **viz.py** — the visual timeline (Gantt), time allocation, daily load.
- **html.py** — a self-contained visual plan (day cards, activity chips).
- **StudyPlannerService** — wires Student Model + graph; `plan()` / `export_html()`.

## CLI

```powershell
ala planner --student ada --days 10 --minutes 60 --html out/plan.html
ala planner --student ada --course applied-dl --days 21
ala planner --benchmark
```

## Configuration (`config/platform.yaml → planner`)

`activity_minutes` (per type) · `revision_gap_days` · `weak_extra_practice` ·
`max_concepts`.

## Benchmark (real graph, isolated learner — no mocks) — `reports/stage20_planner/`

Goal *"master my weak concepts before the final exam"*, deadline 10 days, 60 min/day.

| metric | value |
|---|---|
| days used / deadline | 7 / 10 — **fits** |
| max day load (≤ budget) | **59 / 60 min** |
| total study time | 321 min |
| activities | 21 (read 6 · quiz 6 · practice 3 · revision 6) |
| concepts / weak | 6 / 6 · **100 %** time on weak concepts |
| prerequisite (week) ordered | **True** (Optimizer w1 → … → Clustering w6) |
| unscheduled (over budget) | 0 |

The plan respects the daily budget and deadline, front-loads earlier-week
(prerequisite) concepts, prioritises weak areas, and spaces revision — see
`study_timeline.png` and the self-contained `study_plan.html`.

## Visualizations

`study_timeline` (Gantt) · `time_allocation` · `daily_load` — plus the HTML timeline.

## Tests

[`tests/test_planner.py`](../tests/test_planner.py) — resource bucketing by
doc-type + curriculum week, plan budget/deadline/ordering, weak concept gets more
time + revision (strong doesn't), explicit-goal stats. Full suite **202 passed**.

## Limitations (honest)

- The demo learner is scripted (no real users); the plan, ordering, budgeting and
  revision spacing are real computations over the real concept graph.
- Prerequisite ordering uses each concept's **curriculum week** (a real signal);
  concept-to-concept prerequisite edges (G2) would refine it.
- **Watch** activities appear only where video resources exist (Stage 16 corpus);
  this text/notebook corpus yields mostly read + practice.
- Durations are configured estimates scaled by difficulty, not measured; a single
  core activity may exceed the daily budget on an otherwise empty day.

## Extension hooks

- **RL Adaptive (21):** the policy tunes `minutes_per_day`, activity mix and
  revision gap from the learner's response history.
- **Calendar / notifications (23):** each `StudyDay` maps to a calendar entry via
  Function Calling.
- **GraphRAG:** a quiz activity can invoke the Quiz Agent over the concept's
  evidence.
