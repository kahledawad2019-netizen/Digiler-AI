# Stage 19 — Learning Analytics Dashboard

Turns the Student Model (Stage 18) + concept graph + catalog into learner analytics
and a **self-contained interactive HTML dashboard** plus presentation figures.
Fully **additive** — it reads existing structures, changes none. Package:
[`src/ala/dashboard/`](../src/ala/dashboard/).

## What it shows

progress tracking · knowledge mastery (overall + **by domain**) · **weak-concept
heatmap** · learning timeline · **estimated time spent** · **completion rate** (per
course) · **confidence evolution** (running average) · a **recommendation engine**.

## Architecture

```
StudentModel (mastery, events)  +  ConceptGraph (domains, concept→resource)  +  Catalog (courses)
        │  DashboardBuilder
        ▼
   DashboardData ── RecommendationEngine (review / practice / explore)
        ├── viz.py      → presentation PNG figures
        └── html.py     → self-contained interactive dashboard (SVG charts + tabs)
```

## Components

- **DashboardBuilder** ([builder.py](../src/ala/dashboard/builder.py)) — composes
  Stage-18 analytics with graph-derived domain mastery + heatmap, catalog-derived
  completion, estimated time-spent and confidence evolution.
- **RecommendationEngine** ([recommend.py](../src/ala/dashboard/recommend.py)) —
  grounded advice: review the weakest concepts (with the resources that teach them),
  practise under-attempted concepts, explore `related_to` neighbours of mastered
  concepts.
- **charts.py** — dependency-free inline-**SVG** bar / line / heatmap / donut.
- **html.py** — self-contained dashboard (inline CSS/JS, tabbed: Overview / Mastery
  / Progress / Recommendations; hover tooltips; **no external assets**).
- **viz.py** — PNG figures for the deck.
- **DashboardService** ([service.py](../src/ala/dashboard/service.py)) — wires the
  Student Model + graph + catalog; `build()` / `export_html()`.

## CLI

```powershell
ala dashboard --student ada --html out/ada.html   # interactive dashboard
ala dashboard --student ada                         # summary + recommendations
ala dashboard --benchmark
```

## Configuration (`config/platform.yaml → dashboard`)

`typical_minutes` (per event type, for time-spent estimation) · `recommend_k`.

## Benchmark (real graph + catalog, isolated learner — no mocks)

`reports/stage19_dashboard/`. A demo learner (quizzes + real resource completions):

| analytic | value |
|---|---|
| overall mastery | 0.42 (4 weak · 4 strong · 8 tracked) |
| estimated time spent | **210 min** (quiz 72 · lesson 60 · video 40 · reading 32 · interaction 6) |
| completion | 11 resources across **4 courses**; concept coverage 0.06 |
| mastery by domain | mined 0.13 · statistics 0.13 → ML 0.72 · data-mining 0.72 |
| recommendations | 7 (review weakest 4 + explore 3) |
| confidence points | 24 (running average) |

Deliverables: an interactive **`dashboard.html`** (12.8 KB, self-contained) + 5
figures.

## Visualizations

`mastery_by_domain` · `mastery_heatmap` · `confidence_evolution` ·
`completion_and_time` · `recommendations` — plus the live HTML dashboard.

## Tests

[`tests/test_dashboard.py`](../tests/test_dashboard.py) — recommendation engine
(weak concept + resources), builder (heatmap / domains / time / completion /
confidence / recommendations), SVG chart emitters, and a self-contained-HTML check
(no external assets). Full suite **198 passed**.

## Limitations (honest)

- The learner event stream in the benchmark is **synthetic**; every analytic is a
  real computation over the real concept graph + catalog.
- **Time-spent is estimated** (event type × typical minutes), not measured wall-clock
  — no session timing is collected yet (a clean future signal).
- The heatmap is sparse for a learner who has touched few concepts (8 here); it fills
  in as history grows.
- Charts are inline SVG (no zoom/pan) — deliberately dependency-free and portable.

## Extension hooks

- **Study Planner (20):** consumes `weak_concepts` + `recommendations` + goals + pace.
- **RL Adaptive (21):** the dashboard's mastery/confidence series is the learning
  signal the policy optimises.
- **Session timing:** add `duration_s` to events → real time-spent with no dashboard
  change.
