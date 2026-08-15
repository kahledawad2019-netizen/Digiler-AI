"""Render a self-contained, interactive HTML Learning-Analytics Dashboard.

Inline CSS/JS + inline SVG charts (no external assets). Tabs for Overview /
Mastery / Timeline / Recommendations; hover tooltips on every chart element.
"""

from __future__ import annotations

import html as _h

from ala.dashboard import charts
from ala.dashboard.models import DashboardData

_REC_ICON = {"review": "📘", "practice": "✍️", "explore": "🚀", "prerequisite": "🔑"}


def render(d: DashboardData) -> str:
    p = d.profile
    s = d.summary
    name = _h.escape(p.get("name") or d.student_id)
    kpis = "".join(_kpi(*x) for x in [
        ("overall mastery", f"{s.get('overall_mastery', 0)*100:.0f}%"),
        ("concepts tracked", s.get("n_tracked", 0)),
        ("weak", s.get("n_weak", 0)), ("strong", s.get("n_strong", 0)),
        ("time spent", f"{d.time_spent.get('total_minutes', 0):.0f} min"),
        ("events", s.get("n_events", 0))])

    dm = charts.hbars([(x["domain"], x["mastery"]) for x in d.domain_mastery],
                      colorer=charts.mastery_color)
    hm = charts.heatmap(d.heatmap)
    weak = charts.hbars([(w["concept"], w["mastery"]) for w in d.weak_concepts[:8]],
                        colorer=charts.mastery_color)
    conf = charts.line([c["avg"] for c in d.confidence_evolution], threshold=0.5, color="#4C72B0")
    prog = charts.hbars([(k, v) for k, v in d.progress.items()],
                        maxv=max(d.progress.values(), default=1), colorer=lambda _v: "#8172B3",
                        fmt="{:.0f}")
    comp = "".join(_course_bar(c) for c in d.completion.get("by_course", [])) or \
        f'<p class="muted">concept coverage {d.completion.get("concept_coverage",0)*100:.0f}% ' \
        f'· {d.completion.get("resources_completed",0)} resources completed</p>'
    recs = "".join(_rec(r) for r in d.recommendations)

    return _TMPL.format(
        name=name, level=_h.escape(p.get("level", "")), style=_h.escape(p.get("explanation_style", "")),
        gauge=charts.donut(s.get("overall_mastery", 0)), kpis=kpis,
        domain=dm, heatmap=hm, weak=weak, conf=conf, prog=prog, completion=comp, recs=recs)


def _kpi(label, value):
    return f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>'


def _course_bar(c):
    pct = int(c["rate"] * 100)
    return (f'<div class="crow"><span>{_h.escape(c["course"])}</span>'
            f'<div class="cbar"><i style="width:{pct}%"></i></div>'
            f'<span class="muted">{c["completed"]}/{c["available"]}</span></div>')


def _rec(r):
    res = " · ".join(_h.escape(x["title"][:34]) for x in r.get("resources", [])[:2])
    return (f'<div class="rec"><span class="ic">{_REC_ICON.get(r["kind"],"•")}</span>'
            f'<div><b>{r["kind"].title()}: {_h.escape(r["concept"])}</b> '
            f'<span class="muted">({r["reason"]})</span>'
            f'{"<br><span class=res>"+res+"</span>" if res else ""}</div></div>')


_TMPL = """<!doctype html><html><head><meta charset="utf-8"><title>Learning Dashboard — {name}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}
 header{{background:#111827;color:#fff;padding:18px 26px;display:flex;align-items:center;gap:20px}}
 header h1{{margin:0;font-size:20px}} .sub{{opacity:.8;font-size:13px}}
 .kpis{{display:flex;gap:14px;flex-wrap:wrap;padding:16px 26px}}
 .kpi{{background:#fff;border-radius:10px;padding:12px 18px;box-shadow:0 1px 3px #0001;min-width:96px}}
 .kpi .v{{font-size:22px;font-weight:700}} .kpi .l{{color:#6b7280;font-size:12px}}
 .tabs{{display:flex;gap:6px;padding:0 26px}} .tab{{padding:8px 16px;cursor:pointer;border-radius:8px 8px 0 0;background:#e5e7eb}}
 .tab.on{{background:#fff;font-weight:600}}
 .panel{{display:none;padding:18px 26px}} .panel.on{{display:block}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}}
 .card{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 1px 3px #0001}}
 .card h3{{margin:0 0 10px;font-size:15px}} text.cl{{font-size:12px;fill:#374151}} text.cv{{font-size:11px;fill:#6b7280}}
 text.donut{{font-size:22px;font-weight:700;fill:#111827}} .muted{{color:#9ca3af;font-size:12px}}
 .crow{{display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px}}
 .cbar{{flex:1;height:9px;background:#e5e7eb;border-radius:5px;overflow:hidden}}
 .cbar i{{display:block;height:100%;background:#55A868}}
 .rec{{display:flex;gap:10px;background:#fff;border-radius:10px;padding:10px 12px;margin:8px 0;box-shadow:0 1px 2px #0001}}
 .rec .ic{{font-size:20px}} .res{{color:#2563eb;font-size:12px}}
 .legend{{font-size:12px;color:#6b7280;margin-top:8px}} .sw{{display:inline-block;width:11px;height:11px;border-radius:3px;margin:0 3px 0 10px;vertical-align:middle}}
</style></head><body>
<header>{gauge}<div><h1>📊 Learning Dashboard — {name}</h1>
 <div class="sub">{level} · {style} explanation style</div></div></header>
<div class="kpis">{kpis}</div>
<div class="tabs">
 <div class="tab on" data-t="ov">Overview</div><div class="tab" data-t="ma">Mastery</div>
 <div class="tab" data-t="tl">Progress</div><div class="tab" data-t="re">Recommendations</div></div>

<div class="panel on" id="ov"><div class="grid">
 <div class="card"><h3>Mastery by domain</h3>{domain}</div>
 <div class="card"><h3>Confidence evolution</h3>{conf}<div class="legend">running average of quiz/exam scores</div></div>
 <div class="card"><h3>Weakest concepts</h3>{weak}</div>
 <div class="card"><h3>Completion</h3>{completion}</div>
</div></div>

<div class="panel" id="ma"><div class="card"><h3>Concept-mastery heatmap</h3>{heatmap}
 <div class="legend"><span class="sw" style="background:#C44E52"></span>weak
 <span class="sw" style="background:#DD8452"></span>developing
 <span class="sw" style="background:#55A868"></span>strong</div></div></div>

<div class="panel" id="tl"><div class="card"><h3>Activity by type</h3>{prog}</div></div>

<div class="panel" id="re"><div class="card"><h3>Recommended next steps</h3>{recs}</div></div>

<script>
 document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{{
   document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));
   document.querySelectorAll('.panel').forEach(x=>x.classList.remove('on'));
   t.classList.add('on');document.getElementById(t.dataset.t).classList.add('on');}});
</script></body></html>"""
