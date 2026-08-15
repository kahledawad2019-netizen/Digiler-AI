"""AI Agents — route a request to an agent, or run a study session (existing crew)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/agents", tags=["agents"])


class AskIn(BaseModel):
    text: str
    concept: str | None = None


class SessionIn(BaseModel):
    concept: str
    answer: str | None = None


@router.get("")
async def roster(services: AlaServices = Depends(services_dependency),
                 user: User = Depends(get_current_user)) -> dict:
    """The agent crew + the coordinator's intent-routing table (for the Agents UI)."""
    def _run():
        from ala.agents.coordinator import _INTENT
        svc = services.agent_service
        agents = [{"role": role, "name": getattr(ag, "name", role),
                   "description": getattr(ag, "description", "")}
                  for role, ag in svc.agents.items()]
        routes = [{"role": role.value, "keywords": list(kw)} for kw, role in _INTENT]
        routes.append({"role": "tutor", "keywords": ["(default — anything else)"]})
        return {"agents": agents,
                "coordinator": {"strategy": "deterministic keyword intent routing", "routes": routes},
                "session_flow": ["tutor", "quiz", "evaluator", "planner"]}
    return await run_in_threadpool(_run)


@router.post("/ask")
async def ask(body: AskIn, services: AlaServices = Depends(services_dependency),
              user: User = Depends(get_current_user)) -> dict:
    r = await run_in_threadpool(services.agent_service.ask, body.text,
                                student_id=user.student_id, concept=body.concept)
    return r.to_dict()


@router.post("/session")
async def session(body: SessionIn, services: AlaServices = Depends(services_dependency),
                  user: User = Depends(get_current_user)) -> dict:
    return await run_in_threadpool(services.agent_service.study_session, user.student_id,
                                   body.concept, answer=body.answer)
