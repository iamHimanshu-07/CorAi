"""Authentication: login, register, logout."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.urls import url_parse

from ...extensions import db
from ...models import User

bp = Blueprint("auth", __name__)


@bp.get("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("auth/login.html")


@bp.post("/login")
def login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    remember = bool(request.form.get("remember"))

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        flash("Invalid username or password.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user, remember=remember)
    user.last_login_at = db.func.now()
    db.session.commit()

    next_url = request.args.get("next")
    if not next_url or url_parse(next_url).netloc != "":
        next_url = url_for("main.dashboard")
    return redirect(next_url)


@bp.get("/register")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("auth/register.html")


@bp.post("/register")
def register_post():
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip() or None
    password = request.form.get("password", "")

    if not username or not password:
        flash("Username and password are required.", "danger")
        return redirect(url_for("auth.register"))

    if User.query.filter_by(username=username).first():
        flash("Username already taken.", "danger")
        return redirect(url_for("auth.register"))

    user = User(username=username, role="patient", email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    login_user(user)
    flash("Account created. Welcome.", "success")
    return redirect(url_for("main.dashboard"))


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.home"))