"""Citation Explorer — resolvable, navigable citations for a query."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User
from app.services import chat_service

router = APIRouter(prefix="/citations", tags=["citations"])


class CitationsIn(BaseModel):
    question: str
    top_k: int = 8


@router.post("")
async def citations(body: CitationsIn, services: AlaServices = Depends(services_dependency),
                    user: User = Depends(get_current_user)) -> dict:
    def _run():
        # Citations come from the retrieved evidence package — no LLM generation needed.
        pkg = chat_service.retrieve_package(services, body.question, top_k=body.top_k)
        idx = services.citation_index(pkg)
        return idx.to_dict()
    return await run_in_threadpool(_run)
