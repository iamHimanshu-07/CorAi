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

USER appuser

EXPOSE 10000

# Boot sequence:
#   * Pre-trained model artifact ships in the repo (models/corai-1.0.0.pkl)
#     so Render's free-tier port scan doesn't time out waiting for in-container
#     training to finish.
#   * `flask init-db` is idempotent and runs in <1 s. The `|| echo` lets
#     gunicorn start even if init-db hiccups (e.g. transient DB lock) —
#     `_ensure_schema` in app/__init__.py will lazy-create on first request.
#   * gunicorn binds 0.0.0.0:${PORT} immediately after.
# We use the `app:create_app` form (no parens) — the factory's default
# config_object resolves to `app.config.Config`.
# --preload: load the app once per worker (cheaper RSS than per-process fork
#   when the model artifact and sklearn are heavy).
# --timeout 120: free-tier CPU is slow; first request after cold start can
#   take 30-60 s while sklearn loads.
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["sh", "-c", "\
    flask --app 'app:create_app' init-db || echo 'init-db skipped, will lazy-create'; \
    gunicorn --workers 2 --threads 2 --bind 0.0.0.0:${PORT} --timeout 120 \
             --preload 'app:create_app' \
"]
