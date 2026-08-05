"""Error handlers."""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

log = logging.getLogger(__name__)


def _wants_json() -> bool:
    return request.path.startswith("/v1/") or request.accept_mimetypes.best == "application/json"


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        log.warning(f"400: {e}")
        if _wants_json():
            return jsonify({"error": "bad_request", "message": str(e)}), 400
        return render_template("errors/400.html"), 400

    @app.errorhandler(403)
    def forbidden(e):
        if _wants_json():
            return jsonify({"error": "forbidden", "message": str(e)}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        if _wants_json():
            return jsonify({"error": "not_found", "message": str(e)}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(429)
    def ratelimited(e):
        if _wants_json():
            return jsonify({"error": "rate_limited", "message": str(e)}), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(500)
    def server_error(e):
        log.exception(f"500: {e}")
        if _wants_json():
            return jsonify({"error": "server_error", "message": "Internal server error"}), 500
        return render_template("errors/500.html"), 500
