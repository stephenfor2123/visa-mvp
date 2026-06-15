# Multi-stage Dockerfile for visa-mvp-backend (FastAPI + Python 3.11+)
#
# Stage 1 (builder): install build toolchain (gcc, libffi, etc.) and pre-compile
#                    wheels into a throwaway layer so the runtime image stays slim.
# Stage 2 (runtime): python:3.11-slim only — no compilers, no pip cache,
#                    copy pre-built wheels from builder. Final image ≈ 180MB
#                    instead of ≈ 600MB for a single-stage build with gcc.
#
# Build single arch:
#   docker build -t visa-mvp-backend:dev .
#
# Build multi-arch + push to GHCR (CI runner / dev machine with docker buildx):
#   docker buildx create --use --name multiarch-builder
#   docker buildx build \
#     --platform linux/amd64,linux/arm64 \
#     -t ghcr.io/stephen/visa-api:latest \
#     --push .
#
# Run locally:
#   docker compose up --build

# ---- Stage 1: builder --------------------------------------------------
FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_PREFIX=/install

# Build toolchain — only used in this throwaway stage, NOT carried into runtime.
# libffi-dev / libpq-dev cover bcrypt / psycopg2 / python-jose[cryptography].
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libffi-dev \
        libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy ONLY requirements first — better layer cache (deps don't rebuild on code change).
COPY requirements.txt /build/requirements.txt

# Install into /install (a clean prefix we copy from in stage 2).
# --prefix keeps stage-2 COPY surgical: just /install/lib, /install/bin.
RUN pip install --prefix=/install -r /build/requirements.txt


# ---- Stage 2: runtime --------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH=/install/bin:$PATH

# Runtime-only system deps. NO gcc / build-essential here — image stays small.
# curl: used by healthcheck in docker-compose.yml.
# libpq5: PostgreSQL client lib (kept even though SQLite is the dev DB, so prod
#   swap to Postgres needs no image rebuild).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        libpq5 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy pre-built Python packages from builder (surgical: only /install).
COPY --from=builder /install /usr/local

# App code — COPY after deps for best layer caching.
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY pytest.ini /app/pytest.ini
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# Default: run uvicorn (docker-compose overrides with `alembic upgrade` head).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
