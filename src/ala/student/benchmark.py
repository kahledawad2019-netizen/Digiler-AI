"""Stage 18 — Student-Model benchmark (real graph + retriever, isolated profile).

A demo learner with a **scripted** event stream (no real users exist) drives the
**real** mastery model and the **real** personalised retriever over the **real**
concept graph + hybrid retriever. Everything measured — mastery evolution, weak/
strong separation, and the personalisation effect on retrieval — is a real
computation; only the learner's event inputs are synthetic (and labelled as such).
The production student db is untouched (isolated temp db).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ala.config.settings import Settings
from ala.student.mastery import MasteryModel
from ala.student.model import StudentModel
from ala.student.models import ConceptMastery, EventType, StudentConfig
from ala.student.store import StudentStore

_SID = "demo-learner"
_QUERIES = ["machine learning", "deep learning", "neural networks", "statistics and probability",
            "databases and sql", "model training and evaluation"]


def run_student_benchmark(settings: Settings, *, out_dir: str | Path | None = None) -> Path:
    out = Path(out_dir) if out_dir else (settings.project_root / "reports" / "stage18_student")
    figs = out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    from ala.graph.store import GraphStore
    graph = GraphStore(settings.abspath((settings.graph or {}).get(
        "location", "data/graph/concept_graph.db"))).load()

    weak_ids, strong_ids = _pick_concepts(graph)
    tmp = Path(tempfile.mkdtemp(prefix="ala_student_"))
    model = StudentModel(settings, store=StudentStore(tmp / "student.db"),
                         config=StudentConfig.from_settings(settings))
    model.get_or_create(_SID, name="Demo Learner", level="intermediate",
                        explanation_style="example-driven", goals=["pass the exam"])

    # scripted history — weak concepts answered wrong, strong answered right
    for cid in weak_ids:
        for _ in range(3):
            model.record_quiz(_SID, [cid], correct=False, difficulty=0.6)
        model.record_exposure(_SID, EventType.READING.value, [cid])
    for cid in strong_ids:
        for _ in range(3):
            model.record_quiz(_SID, [cid], correct=True, difficulty=0.6)
        model.record_exposure(_SID, EventType.LESSON.value, [cid])
        model.record_exposure(_SID, EventType.VIDEO.value, [cid])

    summary = model.mastery_summary(_SID)
    weak_now = {cm.concept_id for cm in model.weak_concepts(_SID)}
    strong_now = {cm.concept_id for cm in model.strong_concepts(_SID)}
    separation = {
        "weak_correctly_low": round(sum(c in weak_now for c in weak_ids) / max(1, len(weak_ids)), 3),
        "strong_correctly_high": round(sum(c in strong_now for c in strong_ids) / max(1, len(strong_ids)), 3),
    }

    # mastery evolution (learning curve) for one concept under a realistic sequence
    curve = _learning_curve(model.config)

    # personalisation effect on the real retriever
    personalization = _personalization_effect(settings, model, graph)

    from ala.student.analytics import compute_analytics
    analytics = compute_analytics(model, _SID, graph=graph)
    model.close()

    payload = {"summary": summary, "separation": separation, "learning_curve": curve,
               "personalization": personalization, "analytics": analytics,
               "weak_concepts_seeded": [graph.node(c).label for c in weak_ids if graph.node(c)],
               "strong_concepts_seeded": [graph.node(c).label for c in strong_ids if graph.node(c)]}
    (out / "student.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                      encoding="utf-8")
    from ala.student import viz
    viz.render_all(payload, figs)
    (out / "STUDENT.md").write_text(_markdown(payload), encoding="utf-8")
    return out


# --------------------------------------------------------------------------- #
def _pick_concepts(graph, n_each: int = 3):
    from ala.retrieval.graphsearch.config import PROVENANCE_EDGE_TYPES
    from ala.graph.models import NodeType
    with_res = []
    for cid in graph.nodes(NodeType.CONCEPT.value):
        node = graph.node(cid)
        res = [nb for nb, _e, _d in graph.neighbors(cid, edge_types=PROVENANCE_EDGE_TYPES)
               if nb.startswith("resource:")]
        if len(res) >= 3:
            with_res.append((cid, node.attrs.get("frequency", 0)))
    with_res.sort(key=lambda kv: kv[1], reverse=True)
    top = [c for c, _ in with_res[:12]]
    return top[:n_each], top[n_each:n_each * 2]


def _learning_curve(config: StudentConfig) -> dict:
    mm = MasteryModel(config)
    cm = ConceptMastery(concept_id="demo")
    outcomes = [0, 0, 0, 1, 0, 1, 1, 1, 1]                    # struggle → improvement
    traj = [round(cm.mastery, 3)]
    for o in outcomes:
        mm.update(cm, kind=EventType.QUIZ.value, score=float(o), difficulty=0.6)
        traj.append(round(cm.mastery, 3))
    return {"outcomes": outcomes, "mastery": traj}


def _personalization_effect(settings, model, graph) -> dict:
    from ala.retrieval.search.factory import build_retrievers
    from ala.student.personalize import PersonalizedRetriever
    bundle = build_retrievers(settings)
    try:
        base = bundle.hybrid
        base.retrieve("warmup", top_k=5)
        pers = PersonalizedRetriever(base, model, _SID, graph)
        weak_res = pers.weak_resources

        def coverage(retr):
            covered = 0
            total = 0
            for q in _QUERIES:
                res = retr.retrieve(q, top_k=10)
                total += len(res)
                covered += sum(1 for r in res if r.payload.get("resource_id") in weak_res)
            return round(covered / max(1, total), 4)

        base_cov = coverage(base)
        pers_cov = coverage(pers)
    finally:
        bundle.close()
    return {"n_weak_resources": len(weak_res), "queries": len(_QUERIES),
            "base_weak_coverage@10": base_cov, "personalized_weak_coverage@10": pers_cov,
            "lift": round(pers_cov - base_cov, 4)}


def _markdown(p: dict) -> str:
    s = p["summary"]; sep = p["separation"]; pe = p["personalization"]
    weak = "\n".join(f"| {w['concept']} | {w['mastery']} | {w['attempts']} |"
                     for w in p["analytics"]["weak_concepts"][:8])
    return "\n".join([
        "# Stage 18 — Student Model: Benchmark",
        "",
        "Demo learner (scripted events; all mastery + personalisation are real computations).",
        "",
        f"Seeded weak: {', '.join(p['weak_concepts_seeded'])} · "
        f"strong: {', '.join(p['strong_concepts_seeded'])}.",
        "",
        "## Mastery model",
        "",
        "| metric | value |",
        "|---|---|",
        f"| overall mastery | {s['overall_mastery']} |",
        f"| concepts tracked | {s['n_tracked']} |",
        f"| weak / strong | {s['n_weak']} / {s['n_strong']} |",
        f"| events recorded | {s['n_events']} ({s['events_by_type']}) |",
        f"| seeded-weak correctly classified weak | **{sep['weak_correctly_low']}** |",
        f"| seeded-strong correctly classified strong | **{sep['strong_correctly_high']}** |",
        "",
        "## Learning curve (one concept, quiz sequence "
        f"{p['learning_curve']['outcomes']})",
        f"mastery: {p['learning_curve']['mastery']}",
        "",
        "## Personalised retrieval (weak-concept remediation, real hybrid retriever)",
        "",
        "| metric | value |",
        "|---|---|",
        f"| weak-concept resources | {pe['n_weak_resources']} |",
        f"| base weak-coverage@10 | {pe['base_weak_coverage@10']} |",
        f"| **personalized** weak-coverage@10 | **{pe['personalized_weak_coverage@10']}** |",
        f"| lift | **{pe['lift']:+}** |",
        "",
        "## Weakest concepts",
        "",
        "| concept | mastery | attempts |",
        "|---|---|---|",
        weak,
        "",
        "## Figures (`figures/`)",
        "`student_pipeline` · `mastery_distribution` · `weak_strong_concepts` · "
        "`learning_curve` · `personalization_effect`.",
        "",
        "## Honest notes",
        "- Storage is a **separate** SQLite db (never the KB catalog). The learner's event stream is "
        "synthetic (no real users); the mastery updates, weak/strong classification and retrieval "
        "personalisation are real executions over the real concept graph + hybrid retriever.",
        "- Personalisation boosts resources that teach the learner's weak concepts; the lift depends "
        "on how much the base ranking already covers them.",
        "",
    ])
