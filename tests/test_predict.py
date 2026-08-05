"""JSON API predict tests."""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_input.json"


def _payload():
    return json.loads(FIXTURE.read_text())


def test_predict_happy_path(client):
    rv = client.post("/v1/predict", json=_payload())
    assert rv.status_code == 200
    body = rv.get_json()
    assert 0 <= body["probability"] <= 100
    assert body["risk"] in {"Low", "Moderate", "High"}
    assert body["model_version"]
    assert body["prediction_id"] > 0


def test_predict_validation_error(client):
    bad = _payload()
    bad["Age"] = 999  # out of range
    rv = client.post("/v1/predict", json=bad)
    assert rv.status_code == 400
    body = rv.get_json()
    assert body["error"] == "validation_error"
    assert "details" in body


def test_predict_wrong_category(client):
    bad = _payload()
    bad["ChestPainType"] = "INVALID"
    rv = client.post("/v1/predict", json=bad)
    assert rv.status_code == 400


def test_predict_non_json(client):
    rv = client.post("/v1/predict", data="not json")
    assert rv.status_code == 400
