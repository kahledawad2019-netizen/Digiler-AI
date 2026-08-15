"""iCalendar export — turn a study plan into standard .ics events (offline, stdlib)."""

from __future__ import annotations

from datetime import date, timedelta


def plan_to_ics(plan, *, start: date | None = None, title: str = "Digiler AI Study Plan") -> str:
    start = start or date.today()
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Digiler AI//Study Planner//EN",
             "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{title}"]
    for day in plan.days:
        d = start + timedelta(days=day.day - 1)
        stamp = d.strftime("%Y%m%d")
        concepts = []
        for a in day.activities:
            if a.concept not in concepts:
                concepts.append(a.concept)
        summary = "Study: " + ", ".join(concepts[:3])
        desc = "\\n".join(f"{a.type}: {a.concept} ({a.minutes}m)" for a in day.activities)
        lines += ["BEGIN:VEVENT", f"UID:day{day.day}-{stamp}@digiler.ai",
                  f"DTSTART;VALUE=DATE:{stamp}", f"DTEND;VALUE=DATE:{stamp}",
                  f"SUMMARY:{summary} ({day.minutes} min)", f"DESCRIPTION:{desc}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
