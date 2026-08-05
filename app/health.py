"""Health checks: /healthz (liveness) and /readyz (readiness incl. DB + model)."""

from __future__ import annotations

import logging
from pathlib import Path

from flask import Blueprint, current_app, jsonify

from .extensions import db

log = logging.getLogger(__name__)
bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz():
    """Liveness — process is up. No external deps."""
    return jsonify({"status": "ok"}), 200


@bp.get("/readyz")
def readyz():
    """Readiness — DB reachable and model loadable."""
    checks = {"db": "unknown", "model": "unknown"}
    try:
        db.session.execute(db.text("SELECT 1"))
        checks["db"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["db"] = f"fail: {exc}"

    try:
        model_path = current_app.config["MODEL_PATH"]
        if Path(model_path).exists():
            checks["model"] = "ok"
        else:
            checks["model"] = f"missing: {model_path}"
    except Exception as exc:  # noqa: BLE001
        checks["model"] = f"fail: {exc}"

    overall_ok = all(v == "ok" for v in checks.values())
    return jsonify({"status": "ok" if overall_ok else "degraded", "checks": checks}), 200 if overall_ok else 503
