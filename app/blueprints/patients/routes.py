"""Patient views have been removed as per requirements."""

from flask import Blueprint, abort

bp = Blueprint("patients", __name__)

# All patient routes return 404 since patient views have been removed
@bp.route("/", defaults={"path": ""})
@bp.route("/<path:path>")
def catch_all(path):
    abort(404)