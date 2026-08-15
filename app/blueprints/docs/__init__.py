from flask import Blueprint

bp = Blueprint("docs", __name__, template_folder="templates")

from . import routes  # noqa: E402,F401  (register routes after bp is defined)
