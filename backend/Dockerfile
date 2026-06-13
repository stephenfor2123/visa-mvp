FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps — build-essential for any wheel that needs compiling.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# App
COPY app /app/app
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
RUN mkdir -p /app/data /app/logs

EXPOSE 8000

# Default: run uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
