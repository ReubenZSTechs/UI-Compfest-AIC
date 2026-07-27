# app/core/middleware.py
"""
Registrasi semua middleware aplikasi: CORS, request ID, dan request
logging (durasi + status code tiap request).
"""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Menempelkan request_id unik ke tiap request (dari header masuk kalau
    ada, atau generate baru) — dipakai untuk korelasi log lintas service
    (mis. saat request ini memicu background job RL optimization).
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method, path, status code, dan durasi tiap request."""

    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000

        request_id = getattr(request.state, "request_id", "-")
        logger.info(
            "%s %s | status=%s | duration=%.1fms | request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


def register_middlewares(app: FastAPI) -> None:
    # Urutan penting: middleware yang ditambahkan terakhir dieksekusi paling luar.
    # CORS harus paling luar supaya preflight request tidak kena logic lain dulu.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
