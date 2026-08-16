"""Database models."""

from __future__ import annotations

from datetime import UTC, datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="doctor")  # doctor | patient | admin
    area = db.Column(db.String(120))  # e.g. "Mumbai, IN" — area / city for doctors
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    last_login_at = db.Column(db.DateTime)

    predictions = db.relationship("Prediction", backref="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_doctor(self) -> bool:
        return self.role == "doctor"

    @property
    def is_patient(self) -> bool:
        return self.role == "patient"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class Patient(db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Float, nullable=False)
    restingbp = db.Column(db.Float, nullable=False)
    cholesterol = db.Column(db.Float, nullable=False)
    fastingbs = db.Column(db.Integer, nullable=False)
    maxhr = db.Column(db.Float, nullable=False)
    oldpeak = db.Column(db.Float, nullable=False)
    sex = db.Column(db.String(8), nullable=False)
    cp = db.Column(db.String(16), nullable=False)
    restecg = db.Column(db.String(16), nullable=False)
    exang = db.Column(db.String(8), nullable=False)
    slope = db.Column(db.String(16), nullable=False)

    risk = db.Column(db.String(16))
    probability = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), index=True)

    # Optional link to a user account
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    owner = db.relationship("User", backref="patients")

    predictions = db.relationship("Prediction", backref="patient", lazy="dynamic")

    __table_args__ = (
        db.Index("ix_patients_owner_date", "owner_id", "created_at"),
    )


class Prediction(db.Model):
    """Audit log of every prediction the system makes."""

    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    probability = db.Column(db.Float, nullable=False)
    risk = db.Column(db.String(16), nullable=False)
    model_version = db.Column(db.String(32), nullable=False)
    input_features = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), index=True)


class PdfReport(db.Model):
    __tablename__ = "pdf_reports"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    patient_name = db.Column(db.String(120))
    address = db.Column(db.String(255))
    parsed_data = db.Column(db.JSON)

    patient_id = db.Column(db.Integer, db.ForeignKey("patients.id"))
    patient = db.relationship("Patient", backref="pdf_reports")


class Doctor(db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    specialty = db.Column(db.String(120), nullable=False)
    area = db.Column(db.String(120), nullable=False)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))

