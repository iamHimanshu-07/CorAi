"""Admin: user list, audit log, role changes."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from ...extensions import db
from ...models import Prediction, User

bp = Blueprint("admin", __name__)


def _admin_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapper


@bp.get("/admin/users")
@_admin_required
def users():
    users_list = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users_list)


@bp.get("/admin/audit")
@_admin_required
def audit():
    page = max(int(request.args.get("page", 1)), 1)
    per_page = 50
    pagination = (
        Prediction.query.order_by(Prediction.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return render_template("admin/audit.html", pagination=pagination)


@bp.post("/admin/users/<int:user_id>/role")
@_admin_required
def change_role(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    new_role = request.form.get("role")
    if new_role not in {"doctor", "patient", "admin"}:
        flash("Invalid role.", "danger")
        return redirect(url_for("admin.users"))
    user.role = new_role
    db.session.commit()
    flash(f"User '{user.username}' is now {new_role}.", "success")
    return redirect(url_for("admin.users"))