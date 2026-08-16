"""Gunicorn config for CorAi on Render free tier.

Why these values:

- workers=1, threads=4: Render free tier is 0.1–0.5 vCPU and 512 MB RAM.
  Multiple workers + --preload used to fork after sklearn/numpy/shap
  were loaded, pushing past 512 MB and SIGKILLing the master before it
  bound $PORT ("No open ports detected" → 502 with x-render-routing:
  no-deploy). One worker + threads avoids the fork and stays under the
  cap.
- timeout=120: free-tier CPU is slow; first request after cold start can
  take 30–60 s while the model artifact is loaded into memory.
- graceful_timeout=30: give in-flight requests time to finish when
  Render sends SIGTERM during a redeploy.
- keepalive=5: short keepalive so Render's load balancer can recycle
  idle connections quickly.
- access log to stdout so Render can capture it.
- preload_app is intentionally OFF — see workers note above.
"""
import os

bind = os.getenv("BIND", "0.0.0.0:{}".format(os.getenv("PORT", "10000")))
workers = int(os.getenv("WEB_CONCURRENCY", "1"))
threads = int(os.getenv("WEB_THREADS", "4"))
timeout = int(os.getenv("GUNICORN_TIMEOUT", "300"))
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.getenv("GUNICORN_KEEPALIVE", "5"))
worker_class = "gthread"
preload_app = False

accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info")
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(L)s'
)
