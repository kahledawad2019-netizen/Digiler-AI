"""Interactive quiz — structured MCQ / True-False / Short-Answer questions."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User
from app.services import quiz_service

router = APIRouter(prefix="/quiz", tags=["quiz"])
log = logging.getLogger("digiler.quiz")


class QuizIn(BaseModel):
    resource_id: str | None = None
    concept: str | None = None
    n: int = 5
    difficulty: str = "medium"


@router.post("")
async def make_quiz(body: QuizIn, services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    def _run():
        concept = body.concept
        if not concept and body.resource_id:
            concept = quiz_service.concept_for_resource(services, body.resource_id)
        if not concept:
            return None
        return quiz_service.generate_quiz(services, concept=concept,
                                          n=max(1, min(body.n, 10)), difficulty=body.difficulty)

    try:
        result = await run_in_threadpool(_run)
    except Exception as exc:                                  # structured error, never a reset
        log.exception("quiz generation crashed")
        raise HTTPException(503, f"Quiz generation failed: {exc}") from exc
    if result is None:
        raise HTTPException(422, "No concept available to quiz on for this resource")
    return result
