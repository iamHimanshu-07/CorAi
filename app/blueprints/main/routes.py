"""Main routes: home and dashboard."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, current_app, render_template
from flask_login import current_user, login_required

from ...models import Patient, Prediction, User

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
    out = {"Low": 0, "Moderate": 0, "High": 0}
    for risk, in Prediction.query.with_entities(Prediction.risk).all():
        if risk in out:
            out[risk] += 1
    return out


@bp.get("/")
def home():
    metrics = _load_model_metrics()
    doctor_staff = (
        User.query.filter_by(role="doctor")
        .order_by(User.created_at.desc())
        .limit(6)
        .all()
    )
    admin_staff = (
        User.query.filter_by(role="admin")
        .order_by(User.created_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "main/home.html",
        total_predictions=Prediction.query.count(),
        total_patients=Patient.query.count(),
        total_doctors=User.query.filter_by(role="doctor").count(),
        total_admins=User.query.filter_by(role="admin").count(),
        doctor_staff=doctor_staff,
        admin_staff=admin_staff,
        risk_counts=_risk_counts(),
        metrics=metrics,
    )


@bp.get("/dashboard")
@login_required
def dashboard():
    recent_patients: list[Patient] = []
    recent_predictions: list[Prediction] = []
    all_my_predictions: list[Prediction] = []
    metrics = _load_model_metrics()

    if current_user.is_doctor or current_user.is_admin:
        recent_patients = (
            Patient.query.order_by(Patient.created_at.desc()).limit(10).all()
        )
        recent_predictions = (
            Prediction.query.order_by(Prediction.created_at.desc()).limit(10).all()
        )
    elif current_user.is_patient:
        # Patients see only predictions they personally made (user_id == them).
        # Predictions are linked to a Patient row that was created on the fly
        # when the form was submitted without an existing patient_id.
        recent_predictions = (
            Prediction.query.filter_by(user_id=current_user.id)
            .order_by(Prediction.created_at.desc())
            .limit(10)
            .all()
        )
        all_my_predictions = (
            Prediction.query.filter_by(user_id=current_user.id)
            .order_by(Prediction.created_at.desc())
            .all()
        )

    return render_template(
        "main/dashboard.html",
        recent_patients=recent_patients,
        recent_predictions=recent_predictions,
        all_my_predictions=all_my_predictions,
        risk_counts=_risk_counts(),
        total_predictions=Prediction.query.count(),
        total_patients=Patient.query.count(),
        metrics=metrics,
    )
