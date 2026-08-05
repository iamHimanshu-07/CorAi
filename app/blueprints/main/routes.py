"""Main routes: home and dashboard."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from flask import Blueprint, current_app, render_template
from flask_login import current_user, login_required

from ...models import Patient, Prediction

bp = Blueprint("main", __name__)


def _load_model_metrics() -> dict | None:
    repo = Path(current_app.root_path).resolve().parents[1]
    p = repo / "ml" / "evaluation" / "report.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None


def _risk_counts() -> dict[str, int]:
    counts: Counter[str] = Counter(Prediction.query.with_entities(Prediction.risk).all())
    out = {"Low": 0, "Moderate": 0, "High": 0}
    for r in counts:
        if r in out:
            out[r] = counts[r]
    return out


@bp.get("/")
def home():
    metrics = _load_model_metrics()
    return render_template(
        "main/home.html",
        total_predictions=Prediction.query.count(),
        total_patients=Patient.query.count(),
        risk_counts=_risk_counts(),
        metrics=metrics,
    )


@bp.get("/dashboard")
@login_required
def dashboard():
    recent_patients: list[Patient] = []
    recent_predictions: list[Prediction] = []
    metrics = _load_model_metrics()

    if current_user.is_doctor or current_user.is_admin:
        recent_patients = (
            Patient.query.order_by(Patient.created_at.desc()).limit(10).all()
        )
        recent_predictions = (
            Prediction.query.order_by(Prediction.created_at.desc()).limit(10).all()
        )
    elif current_user.is_patient:
        recent_predictions = []

    return render_template(
        "main/dashboard.html",
        recent_patients=recent_patients,
        recent_predictions=recent_predictions,
        risk_counts=_risk_counts(),
        total_predictions=Prediction.query.count(),
        total_patients=Patient.query.count(),
        metrics=metrics,
    )
