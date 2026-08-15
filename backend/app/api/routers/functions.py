"""Function Calling — list schemas + dispatch (existing safe runtime)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/functions", tags=["functions"])


class CallIn(BaseModel):
    name: str
    arguments: dict = {}


@router.get("")
async def list_functions(services: AlaServices = Depends(services_dependency),
                         user: User = Depends(get_current_user)) -> dict:
    return {"functions": services.functions.schemas()}


@router.post("/call")
async def call(body: CallIn, services: AlaServices = Depends(services_dependency),
               user: User = Depends(get_current_user)) -> dict:
    # mutating tools (knowledge_update) require instructor/admin
    spec = services.functions.get(body.name)
    if spec is not None and spec.mutating and user.role == "student":
        from fastapi import HTTPException
        raise HTTPException(403, f"'{body.name}' requires instructor/admin")
    r = await run_in_threadpool(services.functions.dispatch, body.name, body.arguments)
    return r.to_dict()
