"""Main routes: home and dashboard."""

from __future__ import annotations

from flask import Blueprint, render_template
from flask_login import current_user, login_required

from ...models import Patient, Prediction

bp = Blueprint("main", __name__)


@bp.get("/")
def home():
    return render_template("main/home.html")


@bp.get("/dashboard")
@login_required
def dashboard():
    recent_patients = []
    recent_predictions = []
    if current_user.is_doctor or current_user.is_admin:
        recent_patients = (
            Patient.query.order_by(Patient.created_at.desc()).limit(10).all()
        )
        recent_predictions = (
            Prediction.query.order_by(Prediction.created_at.desc()).limit(10).all()
        )
    elif current_user.is_patient:
        # Patients see only predictions tied to them (none today — patient->prediction linkage is Phase 2)
        recent_predictions = []
    return render_template(
        "main/dashboard.html",
        recent_patients=recent_patients,
        recent_predictions=recent_predictions,
    )