"""Instructor panel — cohort analytics + content overview (role: instructor|admin).

Reads the registered students from the web DB and their mastery from the existing
Student Model (read-only: mastery/weak/strong summaries), and the content inventory
from the knowledge catalog. Aggregation only — no learner logic is re-implemented.
"""

from __future__ import annotations

import json
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db.base import get_session
from app.deps.auth import require_role
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/instructor", tags=["instructor"])


async def _student_users(session: AsyncSession) -> list[User]:
    return list((await session.execute(
        select(User).where(User.role == "student").order_by(User.name))).scalars().all())


@router.get("/students")
async def cohort(_who: User = Depends(require_role("instructor", "admin")),
                 session: AsyncSession = Depends(get_session),
                 services: AlaServices = Depends(services_dependency)) -> dict:
    users = await _student_users(session)

    def _rows():
        sm = services.student_model
        out = []
        for u in users:
            s = sm.mastery_summary(u.student_id)          # read-only; empty for new students
            out.append({"student_id": u.student_id, "name": u.name, "email": u.email,
                        "overall_mastery": s["overall_mastery"], "n_tracked": s["n_tracked"],
                        "n_weak": s["n_weak"], "n_strong": s["n_strong"], "n_events": s["n_events"]})
        out.sort(key=lambda r: (r["n_events"] == 0, r["overall_mastery"]))
        return out
    return {"students": await run_in_threadpool(_rows)}


@router.get("/student/{student_id}")
async def student_detail(student_id: str,
                         _who: User = Depends(require_role("instructor", "admin")),
                         services: AlaServices = Depends(services_dependency)) -> dict:
    def _run():
        sm = services.student_model
        return {"student_id": student_id, "summary": sm.mastery_summary(student_id),
                "weak": [{"concept": c.concept_id, "mastery": round(c.mastery, 4)}
                         for c in sm.weak_concepts(student_id, k=15)],
                "strong": [{"concept": c.concept_id, "mastery": round(c.mastery, 4)}
                           for c in sm.strong_concepts(student_id, k=15)]}
    return await run_in_threadpool(_run)


@router.get("/overview")
async def overview(_who: User = Depends(require_role("instructor", "admin")),
                   session: AsyncSession = Depends(get_session),
                   services: AlaServices = Depends(services_dependency)) -> dict:
    users = await _student_users(session)

    def _run():
        sm = services.student_model
        active, masteries, weak_counter = 0, [], Counter()
        for u in users:
            s = sm.mastery_summary(u.student_id)
            if s["n_events"] > 0:
                active += 1
                masteries.append(s["overall_mastery"])
            for c in sm.weak_concepts(u.student_id, k=20):
                weak_counter[c.concept_id] += 1
        # mastery distribution across active learners
        buckets = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
        for m in masteries:
            idx = min(int(m * 5), 4)
            buckets[list(buckets)[idx]] += 1
        avg = round(sum(masteries) / len(masteries), 4) if masteries else 0.0
        common_weak = [{"concept": c, "students": n} for c, n in weak_counter.most_common(10)]

        # content inventory from the catalog
        from ala.metadata.schema import ResourceMetadata
        metas = [ResourceMetadata.from_dict(json.loads(r["metadata_json"]))
                 for r in services.catalog.list_all(record_status="active")]
        by_type = Counter(str(m.doc_type) for m in metas)
        by_course = Counter(m.course for m in metas)
        return {
            "students": {"registered": len(users), "active": active, "avg_mastery": avg,
                         "mastery_distribution": buckets},
            "common_weak_concepts": common_weak,
            "content": {"resources": len(metas), "by_type": dict(by_type),
                        "by_course": dict(by_course.most_common(12))},
        }
    return await run_in_threadpool(_run)


@router.get("/content")
async def content_inventory(_who: User = Depends(require_role("instructor", "admin")),
                            services: AlaServices = Depends(services_dependency)) -> dict:
    def _run():
        from ala.metadata.schema import ResourceMetadata
        metas = [ResourceMetadata.from_dict(json.loads(r["metadata_json"]))
                 for r in services.catalog.list_all(record_status="active")]
        by_type = Counter(str(m.doc_type) for m in metas)
        courses: dict = {}
        for m in metas:
            c = courses.setdefault(m.course, {"course": m.course, "resources": 0, "modules": set()})
            c["resources"] += 1
            c["modules"].add(m.module or "misc")
        rows = [{"course": c["course"], "resources": c["resources"], "modules": len(c["modules"])}
                for c in courses.values()]
        rows.sort(key=lambda r: r["resources"], reverse=True)
        return {"total": len(metas), "by_type": dict(by_type), "courses": rows}
    return await run_in_threadpool(_run)
