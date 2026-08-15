"""Model metrics page — surfaces the contents of ml/evaluation/report.json."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user, login_required

from ...extensions import db

bp = Blueprint("metrics", __name__)


# Background training state — admin can trigger a retrain from the UI
# without needing Render shell access. Status is exposed to /metrics/train_status.
_train_lock = threading.Lock()
_train_status: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "ok": None,
    "error": None,
    "log_tail": [],
}


def _report_path() -> Path:
    # root_path is <app_dir>/app
    app_root = Path(current_app.root_path)
    # Check parent directory (repo root)
    repo_root = app_root.parent
    p = repo_root / "ml" / "evaluation" / "report.json"
    if p.exists():
        return p
    # Fallback checks
    p2 = app_root / "ml" / "evaluation" / "report.json"
    if p2.exists():
        return p2
    return p


def _load_report() -> dict | None:
    p = _report_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@bp.get("/metrics")
@bp.get("/metrics/")
def show():
    report = _load_report()
    if report is None:
        counts = {"Low": 0, "Moderate": 0, "High": 0}
        try:
            for r, c in db.session.execute(
                db.text("SELECT risk, COUNT(*) FROM predictions GROUP BY risk")
            ).all():
                counts[r if r in counts else "Moderate"] = c
        except Exception:
            pass
        total = sum(counts.values())
        return render_template("metrics/empty.html", counts=counts, total=total)
    # Enrich best_model with its full metrics for template access
    if report and isinstance(report, dict):
        best = report.get("best_model", {})
        if best:
            # Find the corresponding model entry to copy metrics
            for mdl in report.get("models", []):
                if mdl.get("name") == best.get("name"):
                    best["metrics"] = mdl.get("metrics", {})
                    break
            # Ensure the enriched best_model is placed back (modifies in place)
            report["best_model"] = best
    return render_template("metrics/show.html", report=report)


@bp.get("/metrics/<path:artifact>")
def artifact(artifact: str):
    """Serve per-model PNGs and SHAP summary from ml/evaluation/."""
    if ".." in artifact:
        abort(404)
    repo_root = Path(current_app.root_path).parent
    base = (repo_root / "ml" / "evaluation").resolve()
    out = (base / artifact).resolve()
    if not out.exists():
        # Fallback check
        base = (Path(current_app.root_path) / "ml" / "evaluation").resolve()
        out = (base / artifact).resolve()
    if not out.exists():
        abort(404)
    from flask import send_file
    return send_file(out)


# --------------------------------------------------------------------------- #
# Admin: trigger a model retrain from the UI.
#
# On Render free tier you don't have shell access, so the metrics page would
# stay empty until someone commits a fresh report.json + PNGs. This route
# lets an admin run ``python -m ml.train`` in-process inside the web worker
# (via ml.train.train_pipeline), so /metrics picks up new diagnostics after
# the run finishes.
#
# Training runs in a background thread so the request can return immediately
# with a "training started" flash. Status is polled via /metrics/train_status.
# Render free has 512 MB RAM — the pipeline uses ~300-400 MB peak (sklearn +
# SMOTE + matplotlib), so this can OOM if anything else is loaded. We guard
# with the lock to prevent concurrent runs.
# --------------------------------------------------------------------------- #
def _admin_required(view):
    from functools import wraps
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


def _run_train(data_path: str, version: str) -> None:
    """Background worker that runs the training pipeline."""
    import logging
    from datetime import UTC, datetime

    log = logging.getLogger("corai.metrics.retrain")

    def _emit(msg: str) -> None:
        with _train_lock:
            _train_status["log_tail"].append(msg)
            # Keep the tail bounded — last 50 lines is plenty for the UI.
            if len(_train_status["log_tail"]) > 50:
                _train_status["log_tail"] = _train_status["log_tail"][-50:]

    try:
        _emit(f"[{datetime.now(UTC).isoformat()}] Starting training (version={version})")
        # Import lazily so the metrics blueprint can still load on Render free
        # (where training deps are present but heavy).
        from ml.train import train_pipeline  # noqa: PLC0415
        report = train_pipeline(version=version, data_path=Path(data_path))
        _emit(f"[{datetime.now(UTC).isoformat()}] Training finished. best_model={report.get('best_model', {}).get('name')}")
        with _train_lock:
            _train_status["ok"] = True
    except Exception as exc:  # noqa: BLE001
        log.exception("Retrain failed")
        _emit(f"[error] {exc!r}")
        with _train_lock:
            _train_status["ok"] = False
            _train_status["error"] = repr(exc)
    finally:
        with _train_lock:
            _train_status["running"] = False
            _train_status["finished_at"] = datetime.now(UTC).isoformat()


@bp.post("/metrics/retrain")
@_admin_required
def retrain():
    """Kick off a background retrain. Admins only."""
    with _train_lock:
        if _train_status["running"]:
            flash("A retrain is already running — check /metrics/train_status.", "warning")
            return redirect(url_for("metrics.show"))
        data_path = current_app.config.get("CorAi_TRAIN_DATA", "heart.csv")
        version = current_app.config.get("CorAi_MODEL_VERSION", "1.0.0")
        _train_status.update({
            "running": True,
            "started_at": None,
            "finished_at": None,
            "ok": None,
            "error": None,
            "log_tail": [],
            "version": version,
            "data_path": data_path,
        })

    from datetime import UTC, datetime
    with _train_lock:
        _train_status["started_at"] = datetime.now(UTC).isoformat()

    thread = threading.Thread(
        target=_run_train,
        args=(data_path, version),
        name="corai-retrain",
        daemon=True,
    )
    thread.start()
    flash(
        f"Retrain started (version={version}, data={data_path}). "
        "Refresh /metrics in 30-90 s — Render free is slow.",
        "info",
    )
    return redirect(url_for("metrics.show"))


@bp.get("/metrics/train_status")
@_admin_required
def train_status():
    """JSON snapshot of the in-flight or last retrain."""
    with _train_lock:
        return {
            "running": _train_status["running"],
            "started_at": _train_status.get("started_at"),
            "finished_at": _train_status.get("finished_at"),
            "ok": _train_status.get("ok"),
            "error": _train_status.get("error"),
            "version": _train_status.get("version"),
            "data_path": _train_status.get("data_path"),
            "log_tail": list(_train_status.get("log_tail", [])),
        }
