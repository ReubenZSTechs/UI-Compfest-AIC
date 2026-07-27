# Dockerfile
FROM python:3.12-slim AS base

# Env dasar Python: jangan bikin .pyc, jangan buffer stdout (biar log
# langsung muncul di `docker compose logs`)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq-dev + gcc dibutuhkan untuk build psycopg2 (dipakai Alembic sync
# driver); asyncpg tidak butuh ini karena pure-Python + C extension prebuilt.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Jalan sebagai non-root user — praktik keamanan dasar untuk container
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]