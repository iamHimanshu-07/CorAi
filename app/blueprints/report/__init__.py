from flask import Blueprint

bp = Blueprint('report', __name__)

from . import routes
