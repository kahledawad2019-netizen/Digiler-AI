"""Learning Analytics Dashboard (belongs to the profile)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
async def dashboard(services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    def _run():
        services.student_model.get_or_create(user.student_id, name=user.name)
        data = services.dashboard.build(user.student_id).to_dict()
        # Surface the existing Stage-19 RecommendationEngine (reused over the shared
        # graph + student model) — the profile's "next steps" card consumes this.
        from ala.dashboard.recommend import RecommendationEngine
        recs = RecommendationEngine(services.graph, services.student_model).recommend(user.student_id)
        data["recommendations"] = [r.to_dict() for r in recs]
        return data
    return await run_in_threadpool(_run)
