"""Operator / deployment docs.

A short, plain-English guide to:
  1. Generating the model evaluation report (the /metrics page).
  2. Where to put env vars on Render.

These are the questions a new operator asks first, so we surface them
inside the running app rather than burying them in the README.
"""

from __future__ import annotations

import os

from flask import Blueprint, render_template

from . import bp


@bp.get("/docs")
@bp.get("/docs/")
def index():
    """Operator-facing deployment guide."""
    return render_template(
        "docs/index.html",
        render_free=os.getenv("RENDER", "").lower() == "true",
    )
