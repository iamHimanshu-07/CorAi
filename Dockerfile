# syntax=docker/dockerfile:1.7
# ----------------------------------------------------------------------------
# CorAi — production image for Render (free web service).
#
# Render sets PORT (usually 10000) at runtime and expects one process bound
# to 0.0.0.0:$PORT. gunicorn honors $PORT directly.
#
# On every boot (cold start after free-tier spin-down, or redeploy) we:
#   1. Initialize the SQLite DB (idempotent).
#   2. Train the model artifact if missing (~10 s on UCI heart disease).
#   3. Start gunicorn against the Flask app factory.
#
# No persistent disk on free tier, so step 2 re-runs each cold start. That's
# acceptable for a portfolio/demo app.
# ----------------------------------------------------------------------------

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Render injects $PORT; default to 10000 for local sanity checks.
    PORT=10000

# OS deps for heavy wheels (numpy/pandas/scikit-learn/lightgbm/shap/faiss).
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

USER appuser

EXPOSE 10000

# Boot sequence:
#   * init-db creates tables on first run, idempotent afterwards
#   * ml.train is no-op if the artifact at MODEL_PATH already exists
#   * gunicorn binds 0.0.0.0:$PORT (Render sets $PORT)
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["sh", "-c", "\
    flask --app 'app:create_app()' init-db && \
    python -m ml.train --data heart.csv --version 1.0.0 && \
    gunicorn --workers 2 --threads 2 --bind 0.0.0.0:${PORT} --timeout 120 \
             'app:create_app()' \
"]
