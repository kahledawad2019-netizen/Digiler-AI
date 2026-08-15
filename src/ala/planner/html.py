"""Self-contained HTML study-plan timeline (inline CSS, no external assets)."""

from __future__ import annotations

import html as _h

from ala.planner.models import StudyPlan

_ACT = {"read": ("📖", "#4C72B0"), "watch": ("🎬", "#DD8452"), "practice": ("✍️", "#C44E52"),
        "quiz": ("❓", "#8172B3"), "revision": ("🔁", "#55A868")}


def render(plan: StudyPlan, student_id: str) -> str:
    s = plan.stats
    days = "".join(_day(d) for d in plan.days)
    return _TMPL.format(
        goal=_h.escape(plan.goal), student=_h.escape(student_id),
        days_used=s.get("n_days_used"), deadline=s.get("deadline_days"),
        total=plan.total_minutes, weak=int(s.get("weak_minutes_share", 0) * 100),
        fits="✓" if s.get("fits_deadline") else "✗", day_cards=days,
        unscheduled=(f'<p class="muted">Deferred (over budget): {len(plan.unscheduled)} items</p>'
                     if plan.unscheduled else ""))


def _day(d) -> str:
    chips = "".join(
        f'<div class="chip" style="border-left:4px solid {_ACT.get(a.type, ("", "#999"))[1]}">'
        f'{_ACT.get(a.type, ("•", ""))[0]} <b>{a.type}</b> {_h.escape(a.concept[:28])} '
        f'<span class="m">{a.minutes}m</span></div>' for a in d.activities)
    return (f'<div class="day"><div class="dh">Day {d.day} '
            f'<span class="muted">· {d.minutes} min</span></div>{chips}</div>')


_TMPL = """<!doctype html><html><head><meta charset="utf-8"><title>Study Plan — {student}</title>
<style>
 body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:0;background:#f4f6f8;color:#1f2937}}
 header{{background:#111827;color:#fff;padding:18px 26px}} header h1{{margin:0;font-size:20px}}
 .sub{{opacity:.85;font-size:13px;margin-top:4px}}
 .kpis{{display:flex;gap:22px;padding:12px 26px;color:#374151;font-size:14px;flex-wrap:wrap}}
 .kpis b{{font-size:18px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px;padding:16px 26px}}
 .day{{background:#fff;border-radius:12px;padding:12px;box-shadow:0 1px 3px #0001}}
 .dh{{font-weight:700;margin-bottom:8px}} .muted{{color:#9ca3af;font-weight:400;font-size:12px}}
 .chip{{background:#f9fafb;border-radius:8px;padding:6px 9px;margin:5px 0;font-size:13px}}
 .chip .m{{float:right;color:#6b7280;font-size:12px}}
</style></head><body>
<header><h1>🗓️ Study Plan — {student}</h1><div class="sub">{goal}</div></header>
<div class="kpis"><span><b>{days_used}</b>/{deadline} days</span>
 <span><b>{total}</b> min total</span><span><b>{weak}%</b> on weak concepts</span>
 <span>fits deadline {fits}</span></div>
{unscheduled}
<div class="grid">{day_cards}</div>
</body></html>"""
