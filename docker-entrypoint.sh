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

# Render injects PORT at runtime (usually 10000). Fall back explicitly so a
# missing/misconfigured env never leaves gunicorn bound to nothing (which
# surfaces as "No open ports detected" / 502 on Render).
: "${PORT:=10000}"
export PORT

# 1. Idempotent DB init. If it hiccups (e.g. transient DB lock), fall back to
#    lazy schema creation on first request (`_ensure_schema` in app/__init__.py).
flask --app 'app:create_app()' init-db || echo 'init-db skipped, will lazy-create'

# 2. Start gunicorn. Tuned for Render free tier (see gunicorn.conf.py):
#    - workers=1, threads=4 (no --preload): keeps the master under 512 MB
#      so it can bind $PORT before being OOM-killed.
#    - graceful_timeout=30: in-flight requests finish cleanly on SIGTERM.
exec gunicorn --config gunicorn.conf.py 'app:create_app()'
