# app/core/exceptions.py
"""
Custom exception classes + registrasi handler-nya ke FastAPI app.

Tujuan: service.py/repository.py melempar exception domain-spesifik
(mis. WorkerNotFoundError) tanpa perlu tahu soal HTTP status code —
konversi ke response HTTP dilakukan terpusat di sini.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Custom exception classes
# =============================================================================

class AppError(Exception):
    """Base class untuk semua custom exception di aplikasi ini."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    default_message: str = "Terjadi kesalahan."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    default_message = "Resource tidak ditemukan."


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    default_message = "Terjadi konflik data."


class ValidationAppError(AppError):
    """Untuk validasi domain-level yang tidak tertangkap Pydantic, mis. cross-field business rule."""

    status_code = 422  # setara HTTP_422_UNPROCESSABLE_ENTITY; ditulis literal karena nama konstanta berubah antar versi Starlette
    default_message = "Data tidak valid."


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_message = "Autentikasi diperlukan."


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    default_message = "Tidak memiliki akses."


class ExternalServiceError(AppError):
    """Dipakai saat panggilan ke RL engine / LLM API gagal."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_message = "Layanan eksternal tidak merespons dengan benar."


# =============================================================================
# Handlers
# =============================================================================

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "AppError ditangani | path=%s | type=%s | message=%s",
        request.url.path,
        type(exc).__name__,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": type(exc).__name__, "detail": exc.message},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Safety net terakhir — exception tak terduga tidak boleh bocor
    stack trace mentah ke client.
    """
    logger.exception("Unhandled exception di path=%s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "InternalServerError", "detail": "Terjadi kesalahan internal pada server."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
