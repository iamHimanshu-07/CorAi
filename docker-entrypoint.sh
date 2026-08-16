#!/bin/sh
# ----------------------------------------------------------------------------
# CorAi container entrypoint.
#
# Runs on every boot (cold start after free-tier spin-down, or redeploy):
#   1. Initialize the SQLite DB (idempotent).
#   2. Start gunicorn against the Flask app factory.
#
# The pre-trained model artifact (models/corai-1.0.0.pkl) ships in the repo so
# Render's free-tier port scan doesn't time out waiting for in-container
# training to finish.
#
# Render sets PORT at runtime (usually 10000) and expects one process bound
# to 0.0.0.0:$PORT. gunicorn honors $PORT directly.
# ----------------------------------------------------------------------------
set -e

# 1. Idempotent DB init. If it hiccups (e.g. transient DB lock), fall back to
#    lazy schema creation on first request (`_ensure_schema` in app/__init__.py).
flask --app 'app:create_app()' init-db || echo 'init-db skipped, will lazy-create'

# 2. Start gunicorn. Workers/threads tuned for free-tier (2 vCPU).
#    --preload: load the app once per worker (cheaper RSS than per-process fork
#      when the model artifact and sklearn are heavy).
#    --timeout 120: free-tier CPU is slow; first request after cold start can
#      take 30-60 s while sklearn loads.
exec gunicorn \
    --workers 2 \
    --threads 2 \
    --bind "0.0.0.0:${PORT}" \
    --timeout 120 \
    --preload \
    'app:create_app()'
