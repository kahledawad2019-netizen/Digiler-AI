"""LLM provider status + models (Ollama)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from app.deps.auth import get_current_user
from app.deps.services import AlaServices, services_dependency
from app.models import User

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("")
async def llm_status(services: AlaServices = Depends(services_dependency),
                     user: User = Depends(get_current_user)) -> dict:
    from ala.llm.factory import available_provider
    from ala.llm.provider import LLMConfig
    cfg = LLMConfig.from_settings(services.settings)
    reachable = await run_in_threadpool(lambda: available_provider(services.settings) is not None)
    return {"provider": cfg.provider, "model": cfg.model, "base_url": cfg.base_url,
            "supported": cfg.supported, "reachable": reachable}
