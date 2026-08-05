"""Patient CRUD: list, create, view, delete."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Patient, Prediction

bp = Blueprint("patients", __name__)


def _doctor_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not (current_user.is_doctor or current_user.is_admin):
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@bp.get("/")
@_doctor_required
def list_patients():
    patients = Patient.query.order_by(Patient.created_at.desc()).all()
    return render_template("patients/list.html", patients=patients)


@bp.get("/new")
@_doctor_required
def new_patient():
    return render_template("patients/form.html", patient=None)


@bp.post("/")
@_doctor_required
def create_patient():
    form = request.form
    patient = Patient(
        name=form.get("name", "").strip() or "Unnamed",
        age=float(form.get("age", 0)),
        restingbp=float(form.get("restingbp", 0)),
        cholesterol=float(form.get("cholesterol", 0)),
        fastingbs=int(float(form.get("fastingbs", 0))),
        maxhr=float(form.get("maxhr", 0)),
        oldpeak=float(form.get("oldpeak", 0)),
        sex=form.get("sex", "M"),
        cp=form.get("cp", "ATA"),
        restecg=form.get("restecg", "Normal"),
        exang=form.get("exang", "N"),
        slope=form.get("slope", "Flat"),
        owner_id=current_user.id,
    )
    db.session.add(patient)
    db.session.commit()
    flash(f"Patient '{patient.name}' created.", "success")
    return redirect(url_for("patients.detail", patient_id=patient.id))


@bp.get("/<int:patient_id>")
@_doctor_required
def detail(patient_id: int):
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        abort(404)
    predictions = patient.predictions.order_by(Prediction.created_at.desc()).all()
    return render_template("patients/detail.html", patient=patient, predictions=predictions)


@bp.get("/<int:patient_id>/edit")
@_doctor_required
def edit(patient_id: int):
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        abort(404)
    return render_template("patients/form.html", patient=patient)


@bp.post("/<int:patient_id>/edit")
@_doctor_required
def update(patient_id: int):
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        abort(404)
    form = request.form
    patient.name = form.get("name", patient.name).strip() or patient.name
    patient.age = float(form.get("age", patient.age))
    patient.restingbp = float(form.get("restingbp", patient.restingbp))
    patient.cholesterol = float(form.get("cholesterol", patient.cholesterol))
    patient.fastingbs = int(float(form.get("fastingbs", patient.fastingbs)))
    patient.maxhr = float(form.get("maxhr", patient.maxhr))
    patient.oldpeak = float(form.get("oldpeak", patient.oldpeak))
    patient.sex = form.get("sex", patient.sex)
    patient.cp = form.get("cp", patient.cp)
    patient.restecg = form.get("restecg", patient.restecg)
    patient.exang = form.get("exang", patient.exang)
    patient.slope = form.get("slope", patient.slope)
    db.session.commit()
    flash(f"Patient '{patient.name}' updated.", "success")
    return redirect(url_for("patients.detail", patient_id=patient.id))


@bp.post("/<int:patient_id>/delete")
@_doctor_required
def delete(patient_id: int):
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        abort(404)
    db.session.delete(patient)
    db.session.commit()
    flash(f"Patient '{patient.name}' deleted.", "info")
    return redirect(url_for("patients.list_patients"))
