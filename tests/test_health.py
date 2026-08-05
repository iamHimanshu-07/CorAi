"""Health endpoint smoke tests."""

from __future__ import annotations


def test_healthz(client):
    rv = client.get("/healthz")
    assert rv.status_code == 200
    assert rv.get_json() == {"status": "ok"}


def test_readyz_with_model(client):
    rv = client.get("/readyz")
    body = rv.get_json()
    assert "checks" in body
    assert body["checks"]["db"] == "ok"
    # Model path may point to a tmp file or repo file — either is "ok" if it exists
    assert body["checks"]["model"] == "ok"