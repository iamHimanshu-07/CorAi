# syntax=docker/dockerfile:1.7
# ============================================================================
# CorAi — production image
# Used by:
#   - local dev:  docker compose up --build
#   - Render:     web service with `runtime: docker` (this file)
#   - Railway:    builder=Dockerfile
# ============================================================================
ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONWARNINGS=ignore \
    # On hosted PaaS we don't want loky/joblib to spawn worker pools sized
    # to the host's CPU count — pin to a sensible default.
    LOKY_MAX_CPU_COUNT=2 \
    # Don't start a useless X server inside headless reportlab/matplotlib.
    MPLBACKEND=Agg

WORKDIR /app

# system deps: build-essential for scikit-learn / lightgbm wheels, curl for
# healthchecks, libgomp1 for lightgbm runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps (cached separately for better layer reuse) ----
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- Application source ----
COPY . .

# Persistent data directory. On Render we attach a disk at /data (see render.yaml).
# Locally this just falls back to the in-image path, which is fine for dev.
RUN mkdir -p /data/models /data/instance /data/.rag_cache /data/.hf_cache \
    && chmod -R 0777 /data

# Non-root user for the runtime stage.
RUN useradd --create-home --shell /bin/bash corai \
    && chown -R corai:corai /app /data
USER corai

EXPOSE 5000

# ============================================================================
# Entrypoint
# ============================================================================
# On first boot:
#   1. Train the model artifact if missing (uses heart.csv from the repo).
#   2. Initialize the SQLite schema + run the additive migrations.
#   3. Launch gunicorn on $PORT (Render / Railway / Heroku set this).
#
# Subsequent boots skip steps 1 & 2 because the artifact + DB live on the
# persistent volume (/data) and are reused.
# ============================================================================
CMD ["sh", "-c", "\
    set -e; \
    if [ ! -f \"$MODEL_PATH\" ]; then \
        echo '[entrypoint] Training model artifact at $MODEL_PATH ...'; \
        LOKY_MAX_CPU_COUNT=2 python -m ml.train --data heart.csv --version 1.0.0; \
    else \
        echo '[entrypoint] Model artifact already present at $MODEL_PATH — skipping training.'; \
    fi; \
    echo '[entrypoint] Running init-db ...'; \
    flask --app wsgi:app init-db; \
    echo '[entrypoint] Starting gunicorn on port $PORT'; \
    exec gunicorn -w 2 -b 0.0.0.0:$PORT wsgi:app; \
"]
