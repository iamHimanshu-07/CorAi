"""Model metrics page — surfaces the contents of ml/evaluation/report.json."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template

from ...extensions import db

bp = Blueprint("metrics", __name__)


def _report_path() -> Path:
    repo = Path(current_app.root_path).resolve().parents[1]
    if not (repo / "ml" / "evaluation" / "report.json").exists():
        repo = repo / "Heart-Disease-Prediction-System"
    return repo / "ml" / "evaluation" / "report.json"


def _load_report() -> dict | None:
    p = _report_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


@bp.get("/metrics/")
def show():
    report = _load_report()
    if report is None:
        counts = {"Low": 0, "Moderate": 0, "High": 0}
        for r, c in db.session.execute(
            db.text("SELECT risk, COUNT(*) FROM predictions GROUP BY risk")
        ).all():
            counts[r if r in counts else "Moderate"] = c
        total = sum(counts.values())
        return render_template("metrics/empty.html", counts=counts, total=total)
    return render_template("metrics/show.html", report=report)


@bp.get("/metrics/<path:artifact>")
def artifact(artifact: str):
    """Serve per-model PNGs and SHAP summary from ml/evaluation/."""
    if ".." in artifact:
        abort(404)
    repo = Path(current_app.root_path).resolve().parents[1]
    if not (repo / "ml" / "evaluation").exists():
        repo = repo / "Heart-Disease-Prediction-System"
    base = (repo / "ml" / "evaluation").resolve()
    out = (base / artifact).resolve()
    if not str(out).startswith(str(base)):
        abort(404)
    if not out.exists():
        abort(404)
    from flask import send_file
    return send_file(out)
