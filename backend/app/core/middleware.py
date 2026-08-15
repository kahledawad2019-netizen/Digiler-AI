"""Request middleware — request id, timing, security headers; + exception handlers."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger("digiler.api")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        t0 = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:                                    # unhandled → 500 (logged)
            log.exception("unhandled error [%s] %s %s", rid, request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Internal server error",
                                                          "request_id": rid})
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time-ms"] = f"{(time.perf_counter() - t0) * 1000:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})
