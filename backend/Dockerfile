# ==========================================
# Stage 1: Builder — install dependencies
# ==========================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Dependencies untuk compile package tertentu (misal psycopg2, bcrypt)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install dependency manager (uv jauh lebih cepat dari pip)
RUN pip install --no-cache-dir uv

# Copy hanya file dependency dulu supaya layer cache efektif
COPY pyproject.toml uv.lock* ./
# Kalau masih pakai requirements.txt:
# COPY requirements.txt .

RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv pip install --no-cache -r pyproject.toml
# Kalau requirements.txt:
# RUN uv pip install --no-cache -r requirements.txt


# ==========================================
# Stage 2: Runtime — image final, ringan
# ==========================================
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime dependency saja (tanpa build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user untuk security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy virtualenv dari builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy source code
COPY --chown=appuser:appuser ./app ./app
COPY --chown=appuser:appuser ./alembic.ini .
COPY --chown=appuser:appuser ./migrations ./migrations

USER appuser

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]