"""Shared fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.models import User


@pytest.fixture(scope="session")
def trained_model_path(tmp_path_factory) -> Path:
    """Train the model once for the session and return the artifact path."""
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")
    pytest.importorskip("pandas")

    repo = Path(__file__).resolve().parents[1]
    heart_csv = repo / "heart.csv"
    if not heart_csv.exists():
        pytest.skip("heart.csv missing; cannot train fixture")

    from ml.train import train_pipeline
    out_dir = tmp_path_factory.mktemp("hdps-models")
    # The model_path is fixed under models/ by train_pipeline; copy it out.
    train_pipeline("1.0.0", heart_csv)
    src = repo / "models" / "hdps-1.0.0.pkl"
    dst = out_dir / "hdps-1.0.0.pkl"
    dst.write_bytes(src.read_bytes())
    return dst


@pytest.fixture(scope="session")
def app(trained_model_path: Path):
    app = create_app(TestConfig)
    app.config.update(MODEL_PATH=str(trained_model_path))
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username="doctor").first():
            u = User(username="doctor", role="doctor", email="doctor@test.local")
            u.set_password("test-password")
            db.session.add(u)
        if not User.query.filter_by(username="alice").first():
            u = User(username="alice", role="patient", email="alice@test.local")
            u.set_password("alice-password")
            db.session.add(u)
        db.session.commit()
    yield app


@pytest.fixture
def client(app) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def doctor_client(client, app):
    with app.test_request_context():
        client.post("/auth/login", data={"username": "doctor", "password": "test-password"})
    return client
