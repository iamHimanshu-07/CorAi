"""Model metrics page — surfaces the contents of ml/evaluation/report.json."""

from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, abort, current_app, render_template

from ...extensions import db

bp = Blueprint("metrics", __name__)


def _report_path() -> Path:
    # root_path is <app_dir>/app
    app_root = Path(current_app.root_path)
    # Check parent directory (repo root)
    repo_root = app_root.parent
    p = repo_root / "ml" / "evaluation" / "report.json"
    if p.exists():
        return p
    # Fallback checks
    p2 = app_root / "ml" / "evaluation" / "report.json"
    if p2.exists():
        return p2
    return p


def _load_report() -> dict | None:
    p = _report_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


@bp.get("/metrics")
@bp.get("/metrics/")
def show():
    report = _load_report()
    if report is None:
        counts = {"Low": 0, "Moderate": 0, "High": 0}
        try:
            for r, c in db.session.execute(
                db.text("SELECT risk, COUNT(*) FROM predictions GROUP BY risk")
            ).all():
                counts[r if r in counts else "Moderate"] = c
        except Exception:
            pass
        total = sum(counts.values())
        return render_template("metrics/empty.html", counts=counts, total=total)
    # Enrich best_model with its full metrics for template access
    if report and isinstance(report, dict):
        best = report.get("best_model", {})
        if best:
            # Find the corresponding model entry to copy metrics
            for mdl in report.get("models", []):
                if mdl.get("name") == best.get("name"):
                    best["metrics"] = mdl.get("metrics", {})
                    break
            # Ensure the enriched best_model is placed back (modifies in place)
            report["best_model"] = best
    return render_template("metrics/show.html", report=report)


@bp.get("/metrics/<path:artifact>")
def artifact(artifact: str):
    """Serve per-model PNGs and SHAP summary from ml/evaluation/."""
    if ".." in artifact:
        abort(404)
    repo_root = Path(current_app.root_path).parent
    base = (repo_root / "ml" / "evaluation").resolve()
    out = (base / artifact).resolve()
    if not out.exists():
        # Fallback check
        base = (Path(current_app.root_path) / "ml" / "evaluation").resolve()
        out = (base / artifact).resolve()
    if not out.exists():
        abort(404)
    from flask import send_file
    return send_file(out)
