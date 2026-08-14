# syntax=docker/dockerfile:1.7
# ----------------------------------------------------------------------------
# CorAi — production image for Hugging Face Spaces (Docker SDK).
# Multi-stage build to keep the final image small.
# ----------------------------------------------------------------------------

# ---------- Stage 1: build wheels in a throwaway layer -------------------------
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /build

# OS build deps for heavy wheels (numpy / pandas / lightgbm / shap / faiss).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        g++ \
        cmake \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only the manifest first to leverage Docker layer cache on deps.
COPY requirements.txt ./

# Build wheels into a local dir we copy to the runtime stage.
RUN pip install --upgrade pip && \
    pip wheel --wheel-dir=/wheels -r requirements.txt

# ---------- Stage 2: lean runtime -----------------------------------------------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # HF Spaces exposes the container on 7860 by default.
    PORT=7860 \
    # HF Spaces sets HOME=/home/user; we don't rely on it, but we set it anyway.
    HOME=/home/user \
    # Tell HF caches where to live so the persistent disk (if attached)
    # actually catches them. On a fresh build with no disk, /data won't
    # exist — config.py falls back to repo-local paths.
    HF_HOME=/data/.hf_cache \
    TRANSFORMERS_CACHE=/data/.hf_cache \
    SENTENCE_TRANSFORMERS_HOME=/data/.hf_cache

# Runtime OS libs only — build deps are dropped.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

WORKDIR /home/user/app

# Install prebuilt wheels from the builder stage.
COPY --from=builder /wheels /wheels
COPY requirements.txt ./requirements.txt
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Bring in the rest of the source.
COPY --chown=appuser:appuser . /home/user/app

# Best-effort persistent dirs. -p on /data even if a disk is attached later;
# config.py checks writability and falls back to repo paths otherwise.
RUN mkdir -p /data/models /data/.rag_cache /data/.hf_cache \
    && chown -R appuser:appuser /data /home/user/app

USER appuser

EXPOSE 7860

# Boot:
#   1. Initialize the DB (idempotent).
#   2. Train the model if the artifact is missing (idempotent; ~10 s for
#      UCI heart disease).
#   3. Start gunicorn against the app factory. 2 workers + threads is plenty
#      for a demo; HF Spaces CPU basic has 2 vCPUs and ~16 GB RAM.
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["sh", "-c", "\
    flask --app 'app:create_app()' init-db && \
    python -m ml.train --data heart.csv --version 1.0.0 || true && \
    gunicorn --workers 2 --threads 2 --bind 0.0.0.0:7860 --timeout 120 \
             'app:create_app()' \
"]
