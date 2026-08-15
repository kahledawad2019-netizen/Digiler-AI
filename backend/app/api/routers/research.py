"""Research Mode — confidence-gated web fallback (approval-only) via the existing controller."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/research", tags=["research"])


class ResearchIn(BaseModel):
    question: str
    save: bool = False          # if true, approved sources grow the Knowledge Base


@router.post("")
async def research(body: ResearchIn, services: AlaServices = Depends(services_dependency),
                   user: User = Depends(get_current_user)) -> dict:
    def _run():
        approve = (lambda _q, _s: True) if body.save else None
        r = services.research.research(body.question, approve=approve, top_k=8)
        return {"answer": r.answer, "confidence": r.confidence.score,
                "needs_web": r.confidence.needs_research, "used_web": r.used_web,
                "sources": r.sources, "citations": r.citations, "ingested": r.ingested}
    return await run_in_threadpool(_run)
