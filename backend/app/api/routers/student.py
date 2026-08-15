"""Student profile — mastery, weak/strong concepts, preferences (Student Model)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/student", tags=["student"])


class Preferences(BaseModel):
    level: str | None = None
    preferred_language: str | None = None
    explanation_style: str | None = None
    difficulty_preference: str | None = None
    learning_pace: str | None = None
    goals: list[str] | None = None


@router.get("")
async def profile(services: AlaServices = Depends(services_dependency),
                  user: User = Depends(get_current_user)) -> dict:
    def _run():
        sm = services.student_model
        sm.get_or_create(user.student_id, name=user.name)
        return {"summary": sm.mastery_summary(user.student_id),
                "weak": [{"concept": c.concept_id, "mastery": c.mastery}
                         for c in sm.weak_concepts(user.student_id, k=10)],
                "strong": [{"concept": c.concept_id, "mastery": c.mastery}
                           for c in sm.strong_concepts(user.student_id, k=10)],
                "profile": sm.profile(user.student_id).to_dict()}
    return await run_in_threadpool(_run)


@router.put("/preferences")
async def update_preferences(body: Preferences, services: AlaServices = Depends(services_dependency),
                             user: User = Depends(get_current_user)) -> dict:
    def _run():
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        p = services.student_model.get_or_create(user.student_id, **fields)
        return p.to_dict()
    return await run_in_threadpool(_run)
