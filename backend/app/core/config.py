# app/core/config.py
"""
Konfigurasi terpusat aplikasi, dibaca dari environment variables (.env).

Semua module lain (db/session.py, core/security.py, dll) mengambil
konfigurasi dari sini — jangan baca os.environ langsung di tempat lain.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project meta
    PROJECT_NAME: str = "Pabrikers Backend"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/pabrikers",
        description="Async SQLAlchemy DSN, mis. postgresql+asyncpg://user:pass@host:5432/db",
    )
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10

    # Security / Auth
    SECRET_KEY: str = Field(
        default="dev-only-change-me-in-env",
        description="Dipakai untuk sign JWT — WAJIB di-override lewat env var saat deploy.",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 jam (1 hari)

    # CORS
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000"]
    CORS_ALLOW_CREDENTIALS: bool = True

    # File upload (untuk digital_twin_ingestion)
    MAX_UPLOAD_SIZE_MB: int = 20
    ALLOWED_TABLE_EXTENSIONS: list[str] = [".xlsx", ".xls", ".csv"]
    ALLOWED_CV_EXTENSIONS: list[str] = [".pdf", ".docx"]
    UPLOAD_TEMP_DIR: str = "/tmp/pabrikers_uploads"

    # Background job (Celery/arq)
    REDIS_URL: str = "redis://localhost:6379/0"

    # External LLM (untuk CV extraction & sintesis)
    ANTHROPIC_API_KEY: str = Field(default="", description="Dikosongkan default; wajib diisi via env var.")
    LLM_MODEL_NAME: str = "claude-sonnet-4-6"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Hugging Face Token (untuk akses model LLM, mis. vLLM container)
    HF_TOKEN: str = Field(default="", description="Hugging Face Token untuk akses model LLM (mis. vLLM container).")

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Cached — Settings hanya dibaca sekali per proses (env vars tidak
    berubah selama app berjalan). Pakai get_settings() di Depends(),
    bukan import `settings` langsung, kalau butuh testability lebih baik.
    """
    return Settings()


# Instance module-level untuk kemudahan import langsung (dipakai main.py)
settings = get_settings()