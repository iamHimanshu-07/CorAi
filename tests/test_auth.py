"""Auth flow tests."""

from __future__ import annotations


def test_login_and_logout(client, app):
    # GET login renders
    rv = client.get("/auth/login")
    assert rv.status_code == 200
    assert b"Sign in" in rv.data

    # POST login
    rv = client.post(
        "/auth/login",
        data={"username": "doctor", "password": "test-password", "remember": "y"},
        follow_redirects=False,
    )
    assert rv.status_code == 302

    # Authenticated dashboard
    rv = client.get("/dashboard", follow_redirects=False)
    assert rv.status_code == 200
    assert b"Dashboard" in rv.data

    # Logout
    rv = client.post("/auth/logout", follow_redirects=False)
    assert rv.status_code == 302


def test_login_bad_password(client):
    rv = client.post(
        "/auth/login",
        data={"username": "doctor", "password": "wrong"},
        follow_redirects=True,
    )
    assert rv.status_code == 200
    assert b"Invalid username or password" in rv.data


def test_register_patient(client, app):
    rv = client.post(
        "/auth/register",
        data={"username": "newbie", "email": "n@t.local", "password": "abcdefgh"},
        follow_redirects=False,
    )
    assert rv.status_code == 302
    with app.app_context():
        from app.models import User
        u = User.query.filter_by(username="newbie").first()
        assert u is not None
        assert u.role == "patient"