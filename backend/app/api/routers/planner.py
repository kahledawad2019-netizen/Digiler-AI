"""Study Planner — adaptive plan + calendar export (existing planner)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/planner", tags=["planner"])


class PlanIn(BaseModel):
    goal: str = "master my weak concepts"
    course: str | None = None
    days: int = 14
    minutes: int = 60


@router.post("")
async def make_plan(body: PlanIn, services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    def _run():
        from ala.planner.models import StudyGoal
        services.student_model.get_or_create(user.student_id, name=user.name)
        plan = services.planner.plan(user.student_id, StudyGoal(
            description=body.goal, course=body.course, deadline_days=body.days,
            minutes_per_day=body.minutes))
        return plan.to_dict()
    return await run_in_threadpool(_run)


@router.get("/calendar")
async def calendar(days: int = 14, minutes: int = 60,
                   services: AlaServices = Depends(services_dependency),
                   user: User = Depends(get_current_user)) -> Response:
    def _run():
        r = services.functions.dispatch("calendar", {"student_id": user.student_id,
                                                      "days": days, "minutes": minutes})
        return r.result.get("ics", "") if r.ok else ""
    ics = await run_in_threadpool(_run)
    return Response(ics, media_type="text/calendar",
                    headers={"Content-Disposition": "attachment; filename=digiler-study-plan.ics"})
