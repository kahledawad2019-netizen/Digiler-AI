"""Digiler AI backend — FastAPI application factory.

A thin transport/auth/persistence/streaming layer over the existing ala platform.
Run:  uvicorn app.main:app --reload   (from the backend/ directory)
Docs: http://localhost:8000/docs
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.middleware import RequestContextMiddleware, install_error_handlers

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio

    from starlette.concurrency import run_in_threadpool

    from app.db.base import init_models
    await init_models()                                      # dev: create tables (prod: Alembic)

    # Pre-warm the ala services (Qdrant + embeddings, ~10-40 s) in the background so the FIRST
    # user request (chat/search/summary) isn't a cold-start wait that looks like a hang.
    async def _warm():
        from app.deps.services import get_services
        try:
            await run_in_threadpool(get_services)
            logging.getLogger("digiler.api").info("ala services pre-warmed")
        except Exception:                                    # noqa: BLE001
            logging.getLogger("digiler.api").warning("service pre-warm failed", exc_info=True)

    asyncio.create_task(_warm())
    logging.getLogger("digiler.api").info("Digiler AI backend ready (v%s)", __version__)
    yield
    from app.deps.services import shutdown_services
    shutdown_services()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Digiler AI", version=__version__, lifespan=lifespan,
                  description="Production API over the Digiler AI (ala) platform.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(RequestContextMiddleware)
    install_error_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/")
    async def root() -> dict:
        return {"service": "Digiler AI", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
