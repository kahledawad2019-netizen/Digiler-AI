"""Stage 19 — Learning-Analytics-Dashboard benchmark (real graph/catalog, isolated).

Scripts a demo learner (quizzes + real resource completions) so every analytic —
mastery, domains, heatmap, completion, time-spent, confidence, recommendations — is
computed for real over the real concept graph + catalog, then exports the figures,
the interactive HTML dashboard and the JSON. Production student db untouched.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ala.config.settings import Settings
from ala.dashboard.service import DashboardService
from ala.student.model import StudentModel
from ala.student.models import EventType, StudentConfig
from ala.student.store import StudentStore

_SID = "demo-learner"


def run_dashboard_benchmark(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage19_dashboard")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    from ala.catalog.repository import KnowledgeCatalog
    from ala.graph.store import GraphStore
    graph = GraphStore(settings.abspath((settings.graph or {}).get(
        "location", "data/graph/concept_graph.db"))).load()
    catalog = KnowledgeCatalog.from_settings(settings)

    tmp = Path(tempfile.mkdtemp(prefix="ala_dash_"))
    model = StudentModel(settings, store=StudentStore(tmp / "student.db"),
                         config=StudentConfig.from_settings(settings))
    _script_learner(model, graph, catalog)

    svc = DashboardService(settings, student_model=model, graph=graph, catalog=catalog)
    try:
        data = svc.build(_SID)
        html_path = out / "dashboard.html"
        svc.export_html(_SID, html_path)
    finally:
        model.close()
        catalog.close()

    (out / "dashboard.json").write_text(json.dumps(data.to_dict(), indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    from ala.dashboard import viz
    viz.render_all(data, figs)
    (out / "DASHBOARD.md").write_text(_markdown(data, html_path), encoding="utf-8")
    return out


def _script_learner(model: StudentModel, graph, catalog) -> None:
    from ala.graph.models import NodeType
    from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
    model.get_or_create(_SID, name="Demo Learner", level="intermediate",
                        explanation_style="example-driven", goals=["pass the final exam"])

    concepts = []
    for cid in graph.nodes(NodeType.CONCEPT.value):
        res = [nb[len("resource:"):] for nb, _e, _d in
               graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES) if nb.startswith("resource:")]
        if res:
            concepts.append((cid, graph.node(cid).attrs.get("frequency", 0), res))
    concepts.sort(key=lambda x: x[1], reverse=True)
    weak, strong = concepts[:4], concepts[4:8]

    for cid, _f, res in weak:
        for _ in range(3):
            model.record_quiz(_SID, [cid], correct=False, difficulty=0.6)
        model.record_exposure(_SID, EventType.READING.value, [cid], ref=res[0])
    for cid, _f, res in strong:
        for _ in range(3):
            model.record_quiz(_SID, [cid], correct=True, difficulty=0.5)
        model.record_exposure(_SID, EventType.LESSON.value, [cid], ref=res[0])
        if len(res) > 1:
            model.record_exposure(_SID, EventType.VIDEO.value, [cid], ref=res[1])
    # a few interactions (asked questions)
    for cid, _f, _r in concepts[:3]:
        model.record_exposure(_SID, EventType.INTERACTION.value, [cid])


def _markdown(d, html_path: Path) -> str:
    dd = d.to_dict()
    s = dd["summary"]; comp = dd["completion"]; ts = dd["time_spent"]
    recs = "\n".join(f"| {r['kind']} | {r['concept']} | {r['reason']} |"
                     for r in dd["recommendations"][:8])
    dom = "\n".join(f"| {x['domain']} | {x['mastery']} | {x['n']} |" for x in dd["domain_mastery"])
    return "\n".join([
        "# Stage 19 — Learning Analytics Dashboard",
        "",
        "Demo learner (scripted events; all analytics are real computations over the real "
        "concept graph + catalog).",
        "",
        "## Summary",
        f"- overall mastery **{s['overall_mastery']}** · tracked {s['n_tracked']} · "
        f"weak {s['n_weak']} · strong {s['n_strong']} · events {s['n_events']}",
        f"- estimated time spent **{ts['total_minutes']:.0f} min** {ts['by_type']}",
        f"- completion: concept coverage {comp['concept_coverage']} · "
        f"{comp['resources_completed']} resources completed",
        "",
        "## Mastery by domain",
        "",
        "| domain | mastery | concepts |",
        "|---|---|---|",
        dom,
        "",
        "## Recommendations (engine)",
        "",
        "| kind | concept | reason |",
        "|---|---|---|",
        recs,
        "",
        "## Deliverables",
        f"- **`{html_path.name}`** — self-contained interactive dashboard (tabs: Overview / Mastery / "
        "Progress / Recommendations; hover tooltips on every chart).",
        "- Figures (`figures/`): `mastery_by_domain` · `mastery_heatmap` · `confidence_evolution` · "
        "`completion_and_time` · `recommendations`.",
        "",
        "## Honest notes",
        "- The learner event stream is synthetic (no real users); every analytic — mastery, domain "
        "roll-up, heatmap, completion, time-spent, confidence, recommendations — is a real "
        "computation over the real concept graph + catalog.",
        "- Time-spent is **estimated** from event type × typical duration (configurable), not measured "
        "wall-clock (no session timing is collected yet).",
        "",
    ])
