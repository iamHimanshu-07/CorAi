"""One-time seed of a default doctor account on first run."""

from __future__ import annotations

import logging

from flask import current_app

from .extensions import db
from .models import User

log = logging.getLogger(__name__)


def seed_default_doctor() -> None:
    username = current_app.config["BOOTSTRAP_DOCTOR_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    doctor = User(
        username=username,
        role="doctor",
        email=current_app.config["BOOTSTRAP_DOCTOR_EMAIL"],
        area=current_app.config.get("BOOTSTRAP_DOCTOR_AREA", "India"),
    )
    doctor.set_password(current_app.config["BOOTSTRAP_DOCTOR_PASSWORD"])
    db.session.add(doctor)
    db.session.commit()
    log.info(f"Seeded default doctor '{username}' (change the password in production!)")
