"""Demo data seeder: fills the DB with realistic sample patients + predictions.

Used in development to give every page something to show. Idempotent — does
nothing if any Patient row already exists.

Trigger:
    flask --app wsgi:app seed-demo
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import click
from flask import Flask
from flask.cli import with_appcontext

from .extensions import db
from .models import Patient, Prediction, User

# Hand-crafted cases spanning Low / Moderate / High risk so all UI states appear.
DEMO_CASES: list[dict] = [
    # name, age, restingbp, chol, fastingbs, maxhr, oldpeak, sex, cp, restecg, exang, slope, expected_risk
    ("Aarav Sharma",      35, 118, 180, 0, 165, 0.0,  "M", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Priya Patel",       42, 124, 210, 0, 158, 0.4,  "F", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Rohan Verma",       48, 128, 220, 0, 152, 0.6,  "M", "NAP", "Normal",  "N", "Flat", "Low"),
    ("Sara Khan",         55, 134, 245, 0, 148, 0.8,  "F", "ATA", "ST",      "N", "Up",   "Low"),
    ("Vikram Singh",      60, 138, 235, 1, 142, 1.0,  "M", "NAP", "LVH",     "N", "Flat", "Moderate"),
    ("Ananya Iyer",       51, 130, 260, 0, 144, 1.2,  "F", "ATA", "Normal",  "N", "Flat", "Moderate"),
    ("Karthik Reddy",     57, 142, 270, 1, 138, 1.4,  "M", "ASY", "ST",      "Y", "Flat", "Moderate"),
    ("Meera Joshi",       63, 140, 250, 1, 135, 1.6,  "F", "ASY", "Normal",  "Y", "Flat", "Moderate"),
    ("Arjun Mehta",       58, 145, 285, 1, 132, 1.8,  "M", "ASY", "ST",      "Y", "Flat", "High"),
    ("Deepa Nair",        66, 150, 295, 1, 128, 2.0,  "F", "ASY", "LVH",     "Y", "Down", "High"),
    ("Rajesh Kumar",      61, 148, 280, 1, 125, 2.2,  "M", "ASY", "ST",      "Y", "Down", "High"),
    ("Lakshmi Rao",       54, 130, 230, 0, 150, 0.5,  "F", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Manoj Tiwari",      45, 126, 215, 0, 160, 0.2,  "M", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Pooja Desai",       39, 120, 195, 0, 170, 0.1,  "F", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Sandeep Yadav",     64, 142, 265, 1, 138, 1.3,  "M", "NAP", "LVH",     "Y", "Flat", "Moderate"),
    ("Kavita Pandey",     52, 132, 240, 0, 146, 0.9,  "F", "NAP", "ST",      "N", "Flat", "Moderate"),
    ("Nikhil Joshi",      59, 140, 260, 1, 140, 1.5,  "M", "ASY", "ST",      "Y", "Flat", "High"),
    ("Ritu Agarwal",      47, 128, 225, 0, 155, 0.6,  "F", "ATA", "Normal",  "N", "Up",   "Low"),
    ("Aditya Bose",       56, 136, 248, 0, 144, 1.0,  "M", "ATA", "LVH",     "N", "Flat", "Moderate"),
    ("Sunita Kapoor",     67, 152, 290, 1, 130, 2.1,  "F", "ASY", "ST",      "Y", "Down", "High"),
]


def _probability_for(risk: str) -> float:
    rng = random.Random(hash(risk))
    if risk == "Low":
        return round(rng.uniform(4.0, 28.0), 2)
    if risk == "Moderate":
        return round(rng.uniform(31.0, 59.0), 2)
    return round(rng.uniform(62.0, 92.0), 2)


@with_appcontext
def _seed() -> None:
    if Patient.query.count() > 0:
        click.echo("Demo data already present; skipping.")
        return

    doctor = User.query.filter_by(role="doctor").first()
    if doctor is None:
        click.echo("No doctor user found; cannot seed.")
        return

    now = datetime.now(UTC)
    for i, case in enumerate(DEMO_CASES):
        (name, age, restingbp, chol, fastingbs, maxhr, oldpeak,
         sex, cp, restecg, exang, slope, risk) = case
        proba = _probability_for(risk)
        ts = now - timedelta(hours=len(DEMO_CASES) - i)
        patient = Patient(
            name=name, age=age, restingbp=restingbp, cholesterol=chol,
            fastingbs=fastingbs, maxhr=maxhr, oldpeak=oldpeak,
            sex=sex, cp=cp, restecg=restecg, exang=exang, slope=slope,
            risk=risk, probability=proba, owner_id=doctor.id,
            created_at=ts,
        )
        db.session.add(patient)
        db.session.flush()
        pred = Prediction(
            patient_id=patient.id, user_id=doctor.id,
            probability=proba, risk=risk, model_version="1.0.0",
            input_features={
                "Age": age, "RestingBP": restingbp, "Cholesterol": chol,
                "FastingBS": fastingbs, "MaxHR": maxhr, "Oldpeak": oldpeak,
                "Sex": sex, "ChestPainType": cp, "RestingECG": restecg,
                "ExerciseAngina": exang, "ST_Slope": slope,
            },
            created_at=ts + timedelta(seconds=2),
        )
        db.session.add(pred)

    db.session.commit()
    click.echo(f"Seeded {len(DEMO_CASES)} demo patients + predictions.")


def register_seed(app: Flask) -> None:
    app.cli.command("seed-demo")(_seed)

    # Auto-run on first request if the DB is empty (dev convenience).
    @app.before_request
    def _autoseed():
        try:
            from flask import has_request_context
            if not has_request_context():
                return
            count = db.session.execute(db.text("SELECT COUNT(*) FROM patients")).scalar() or 0
            if count == 0 and User.query.filter_by(role="doctor").first():
                _seed()
        except Exception:  # noqa: BLE001
            pass
