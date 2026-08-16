# syntax=docker/dockerfile:1.7
# ----------------------------------------------------------------------------
# CorAi — production image for Render (free web service).
#
# Render sets PORT (usually 10000) at runtime and expects one process bound
# to 0.0.0.0:$PORT. gunicorn honors $PORT directly.
#
# On every boot (cold start after free-tier spin-down, or redeploy) we:
#   1. Initialize the SQLite DB (idempotent).
#   2. Start gunicorn against the Flask app factory.
#
# The pre-trained model artifact (models/corai-1.0.0.pkl) ships in the repo so
# boot doesn't have to wait for training. No persistent disk on free tier, but
# the DB and model artifact are both rebuildable on first request if missing.
# ----------------------------------------------------------------------------

FROM python:3.11-slim

# NOTE: do NOT bake PORT into the image. Render injects PORT at runtime
# and a baked default can shadow it. The CMD below reads $PORT directly.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OS deps for heavy wheels (numpy/pandas/scikit-learn/lightgbm/shap).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        cmake \
        libgomp1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user with UID 1000 (matches Render's runtime expectations).
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

WORKDIR /home/appuser/app

# Copy & install Python deps first to leverage Docker layer cache.
COPY --chown=appuser:appuser requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Bring in the rest of the source.
COPY --chown=appuser:appuser . ./

# Make sure caches / runtime dirs are writable by the appuser.
RUN mkdir -p instance models .rag_cache .hf_cache && \
    chown -R appuser:appuser instance models .rag_cache .hf_cache

# Mark the entrypoint as executable (Windows-checked-in files often lose the
# bit, and a non-exec script produces confusing "not found" errors).
RUN chmod +x docker-entrypoint.sh

USER appuser

EXPOSE 10000

# Boot sequence lives in docker-entrypoint.sh so we don't have to wrestle with
# shell-quoting inside the Dockerfile CMD array. Render's build pipeline once
# surfaced `/bin/sh: 1: [sh,: not found` when the inline `CMD ["sh","-c","..."]`
# was malformed — moving the script out of the Dockerfile sidesteps that
# entirely.
# tini reaps zombies and forwards signals to gunicorn for graceful shutdown.
ENTRYPOINT ["/usr/bin/tini", "--", "/home/appuser/app/docker-entrypoint.sh"]
