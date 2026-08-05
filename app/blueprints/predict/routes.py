"""Prediction UI: form, run, PDF report."""

from __future__ import annotations

import io
from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Patient, Prediction
from ...predict import Predictor, features_from_form

bp = Blueprint("predict", __name__)


def _get_predictor() -> Predictor:
    return Predictor.instance(current_app.config["MODEL_PATH"])


@bp.get("/")
@login_required
def form():
    return render_template("predict/form.html", result=None, explanations=None)


@bp.post("/")
@login_required
def run():
    try:
        features = features_from_form(request.form)
    except (KeyError, ValueError, TypeError) as exc:
        flash(f"Invalid input: {exc}", "danger")
        return redirect(url_for("predict.form"))

    predictor = _get_predictor()
    try:
        result = predictor.predict(features)
        explanations = predictor.explain(features)
    except FileNotFoundError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("predict.form"))

    # Persist to DB if a patient_id was provided and the user owns the patient.
    patient = None
    patient_id_raw = request.form.get("patient_id", "").strip()
    if patient_id_raw:
        try:
            patient_id = int(patient_id_raw)
        except ValueError:
            patient_id = None
        if patient_id:
            patient = db.session.get(Patient, patient_id)
            if patient is None:
                flash(f"Patient #{patient_id} not found; prediction saved without patient link.", "warning")
            else:
                # If no patient was supplied, also create a one-shot patient row.
                pass
    if patient is None:
        patient = Patient(
            name=request.form.get("name", "Anonymous"),
            age=features.Age,
            restingbp=features.RestingBP,
            cholesterol=features.Cholesterol,
            fastingbs=features.FastingBS,
            maxhr=features.MaxHR,
            oldpeak=features.Oldpeak,
            sex=features.Sex,
            cp=features.ChestPainType,
            restecg=features.RestingECG,
            exang=features.ExerciseAngina,
            slope=features.ST_Slope,
            risk=result.risk,
            probability=result.probability,
            owner_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(patient)
        db.session.flush()  # need patient.id

    pred_row = Prediction(
        patient_id=patient.id,
        user_id=current_user.id if current_user.is_authenticated else None,
        probability=result.probability,
        risk=result.risk,
        model_version=result.model_version,
        input_features=features.to_dataframe_row(),
    )
    db.session.add(pred_row)
    db.session.commit()

    return render_template(
        "predict/result.html",
        result=result,
        features=features,
        explanations=explanations,
        prediction_id=pred_row.id,
    )


@bp.get("/<int:prediction_id>/pdf")
@login_required
def pdf_report(prediction_id: int):
    pred = db.session.get(Prediction, prediction_id)
    if pred is None:
        abort(404)
    if not (current_user.is_admin or (pred.user_id == current_user.id)):
        abort(403)

    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER, title="HDPS Prediction Report")
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Heart Disease Prediction System", styles["Title"]),
        Paragraph("Prediction Report", styles["Heading2"]),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Generated: {datetime.now(timezone.utc).isoformat()}", styles["Normal"]),
        Paragraph(f"Prediction ID: {pred.id}", styles["Normal"]),
        Paragraph(f"Patient ID: {pred.patient_id}", styles["Normal"]),
        Paragraph(f"Model version: {pred.model_version}", styles["Normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph(f"Probability: {pred.probability:.2f}%", styles["Heading3"]),
        Paragraph(f"Risk band: {pred.risk}", styles["Heading3"]),
        Spacer(1, 0.3 * inch),
        Paragraph("Input features", styles["Heading3"]),
    ]
    for k, v in pred.input_features.items():
        story.append(Paragraph(f"{k}: {v}", styles["Normal"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        Paragraph(
            "Educational use only. Not a clinical diagnosis. See MODEL_CARD.md.",
            styles["Italic"],
        )
    )
    doc.build(story)
    buffer.seek(0)
    from flask import send_file
    return send_file(
        buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"hdps-prediction-{pred.id}.pdf",
    )