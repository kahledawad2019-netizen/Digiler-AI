"""Health + readiness."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "digiler-ai", "version": __version__}


@router.get("/ready")
async def ready() -> dict:
    """Reports whether the retrieval stack + LLM are available (never raises)."""
    from starlette.concurrency import run_in_threadpool
    out = {"retrieval": False, "llm": False, "model": None}
    try:
        from app.deps.services import get_services
        svc = await run_in_threadpool(get_services)
        out["retrieval"] = True
        from ala.llm.provider import LLMConfig
        cfg = LLMConfig.from_settings(svc.settings)
        out["model"] = cfg.model
        from ala.llm.factory import available_provider
        out["llm"] = await run_in_threadpool(lambda: available_provider(svc.settings) is not None)
    except Exception as exc:                                  # not built yet / no artifacts
        out["error"] = str(exc)
    return out
