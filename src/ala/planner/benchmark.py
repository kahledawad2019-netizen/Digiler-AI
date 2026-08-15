"""Stage 20 — Study-Planner benchmark (real graph, isolated learner — no mocks).

Scripts a demo learner with weak concepts, generates a real adaptive plan over the
real concept graph, and verifies the plan is well-formed: budget respected, fits the
deadline, weak concepts prioritised, spaced revision inserted, prerequisite
(curriculum-week) ordering. Production student db untouched.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ala.config.settings import Settings
from ala.planner.models import PlannerConfig, StudyGoal
from ala.planner.service import StudyPlannerService
from ala.student.model import StudentModel
from ala.student.models import EventType, StudentConfig
from ala.student.store import StudentStore

_SID = "demo-learner"


def run_planner_benchmark(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage20_planner")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    from ala.graph.store import GraphStore
    graph = GraphStore(settings.abspath((settings.graph or {}).get(
        "location", "data/graph/concept_graph.db"))).load()

    tmp = Path(tempfile.mkdtemp(prefix="ala_plan_"))
    model = StudentModel(settings, store=StudentStore(tmp / "student.db"),
                         config=StudentConfig.from_settings(settings))
    _script(model, graph)

    goal = StudyGoal(description="master my weak concepts before the final exam",
                     deadline_days=10, minutes_per_day=60)
    svc = StudyPlannerService(settings, student_model=model, graph=graph,
                              config=PlannerConfig.from_settings(settings))
    try:
        plan = svc.plan(_SID, goal)
        html_path = out / "study_plan.html"
        svc.export_html(_SID, goal, html_path)
    finally:
        model.close()

    # prerequisite ordering check: concepts should be non-decreasing in week
    weeks = [c["week"] for c in plan.concepts]
    prereq_ordered = all(weeks[i] <= weeks[i + 1] for i in range(len(weeks) - 1))

    payload = {"goal": plan.goal, "stats": plan.stats,
               "prerequisite_ordered": prereq_ordered,
               "concepts": plan.concepts, "unscheduled": plan.unscheduled,
               "n_days": len(plan.days), "sample_days": [d.to_dict() for d in plan.days[:3]],
               "html": str(html_path)}
    (out / "planner.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    from ala.planner import viz
    viz.render_all(plan, figs)
    (out / "PLANNER.md").write_text(_markdown(payload, plan), encoding="utf-8")
    return out


def _script(model: StudentModel, graph) -> None:
    from ala.graph.models import NodeType
    from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
    model.get_or_create(_SID, name="Demo Learner", level="intermediate",
                        explanation_style="example-driven", learning_pace="normal",
                        goals=["pass the final exam"])
    concepts = [cid for cid in graph.nodes(NodeType.CONCEPT.value)
                if any(nb.startswith("resource:")
                       for nb, _e, _d in graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES))]
    concepts.sort(key=lambda c: graph.node(c).attrs.get("frequency", 0), reverse=True)
    for cid in concepts[:6]:                                  # 6 weak concepts
        for _ in range(3):
            model.record_quiz(_SID, [cid], correct=False, difficulty=0.6)


def _markdown(p: dict, plan) -> str:
    s = p["stats"]
    by = s.get("by_activity", {})
    conc = "\n".join(f"| {c['concept']} | {c['mastery']} | week {c['week'] if c['week'] < 99 else '-'} |"
                     for c in p["concepts"][:10])
    return "\n".join([
        "# Stage 20 — Study Planner: Benchmark",
        "",
        f"Goal: **{p['goal']}** · deadline {s['deadline_days']} days · {s['minutes_per_day']} min/day.",
        "",
        "## Plan quality",
        "",
        "| metric | value |",
        "|---|---|",
        f"| days used / deadline | {s['n_days_used']} / {s['deadline_days']} |",
        f"| fits deadline | **{s['fits_deadline']}** |",
        f"| max day load (≤ budget) | **{s['max_day_minutes']}** / {s['minutes_per_day']} min |",
        f"| total study time | {s['total_minutes']} min |",
        f"| activities | {s['n_activities']} {by} |",
        f"| concepts / weak | {s['n_concepts']} / {s['n_weak']} |",
        f"| time on weak concepts | **{int(s['weak_minutes_share']*100)}%** |",
        f"| prerequisite (week) ordered | **{p['prerequisite_ordered']}** |",
        f"| unscheduled (over budget) | {s['n_unscheduled']} |",
        "",
        "## Concept order (prerequisite week → weakest first)",
        "",
        "| concept | mastery | curriculum week |",
        "|---|---|---|",
        conc,
        "",
        "## Deliverables",
        f"- **`{Path(p['html']).name}`** — self-contained visual study-plan timeline.",
        "- Figures (`figures/`): `study_timeline` · `time_allocation` · `daily_load`.",
        "",
        "## Honest notes",
        "- The learner is a scripted demo (no real users); the plan, ordering, time budgeting and "
        "revision spacing are real computations over the real concept graph.",
        "- Prerequisite ordering uses the **curriculum week** of each concept's resources (a real "
        "signal); concept-to-concept prerequisite edges (G2) would refine it further.",
        "- Activity durations come from config (`planner.activity_minutes`) scaled by concept "
        "difficulty; a single core activity may exceed the daily budget on an otherwise empty day.",
        "",
    ])
