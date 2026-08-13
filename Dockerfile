# syntax=docker/dockerfile:1.7
# ============================================================================
# CorAi — production image
# Used by:
#   - local dev:  docker compose up --build
#   - Render:     web service with `runtime: docker` (this file)
#   - Railway:    builder=Dockerfile
#   - HF Spaces:  Docker Space (sdk: docker, port 7860)
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

# Hugging Face Spaces runs containers as UID 1000 with username `user`.
# Create that user up front so we can drop privileges before any pip install
# or COPY (avoids "Permission denied" on /home/user/.cache/pip).
# We also create the legacy `corai` user as a fallback alias for Render /
# Railway deployments that don't enforce UID 1000.
RUN useradd --create-home --shell /bin/bash --uid 1000 user \
    && useradd --create-home --shell /bin/bash corai || true \
    && mkdir -p /home/user/app \
    && chown -R user:user /home/user

# Default port: 7860 for HF Spaces. Render / Railway set $PORT explicitly,
# so this default is overridden in production.
ENV PORT=7860

WORKDIR /home/user/app

# system deps: build-essential for scikit-learn / lightgbm wheels, curl for
# healthchecks, libgomp1 for lightgbm runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# ---- Python deps (cached separately for better layer reuse) ----
COPY --chown=user:user requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# ---- Application source ----
COPY --chown=user:user . .

# Persistent data directory. On Render / Railway we attach a disk at /data
# (see render.yaml / Procfile). Locally and on free HF Spaces (no Storage
# Bucket) this just falls back to the in-image path, which is fine for dev
# and the model retrains on every cold start.
RUN mkdir -p /data/models /data/instance /data/.rag_cache /data/.hf_cache \
    && chmod -R 0777 /data \
    && chown -R user:user /data /home/user/app

USER user

EXPOSE 7860

# ============================================================================
# Entrypoint
# ============================================================================
# On first boot:
#   1. Train the model artifact if missing (uses heart.csv from the repo).
#   2. Initialize the SQLite schema + run the additive migrations.
#   3. Launch gunicorn on $PORT (Render / Railway / Heroku / HF Spaces set this).
#
# Subsequent boots skip steps 1 & 2 if a persistent volume is mounted at /data
# and the artifact + DB live there.
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
    exec gunicorn -w 1 -b 0.0.0.0:$PORT --timeout 120 wsgi:app; \
"]
