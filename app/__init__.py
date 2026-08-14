"""CorAi application factory."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from .extensions import db, limiter, login_manager, migrate


def create_app(config_object: str | object = "config.Config") -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=False,
        template_folder="templates",
        static_folder="static",
    )

    # Config
    app.config.from_object(config_object)

    # Ensure instance dir exists for sqlite
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Configure RAG engine (HeartAI Copilot) with Gemini API key from config
    try:
        import rag_engine
        # Prefer GOOGLE_API_KEY (current), fall back to legacy GEMINI_API_KEY.
        gemini_key = app.config.get("GOOGLE_API_KEY") or app.config.get("GEMINI_API_KEY")
        if gemini_key:
            # RAG FAISS index lives in the repo-local .rag_cache so it's
            # recreated on cold starts (free-tier friendly).
            rag_engine.configure(
                google_api_key=gemini_key,
                index_dir=os.getenv("CorAi_RAG_INDEX", ".rag_cache/corai_index"),
            )
            app.logger.info("RAG engine configured with Gemini API key")
        else:
            app.logger.warning(
                "GOOGLE_API_KEY/GEMINI_API_KEY not set; HeartAI Copilot will "
                "show a configuration message in the chat widget."
            )
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("RAG engine not available: %s", exc)

    # Blueprints
    from .blueprints.admin.routes import bp as admin_bp
    from .blueprints.api.routes import bp as api_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.fhir.routes import bp as fhir_bp
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.metrics.routes import bp as metrics_bp
    from .blueprints.patients.routes import bp as patients_bp
    from .blueprints.predict.routes import bp as predict_bp
    # New feature blueprints
    from .blueprints.chatbot.routes import bp as chatbot_bp
    from .blueprints.report.routes import bp as report_bp
    from .blueprints.map.routes import bp as map_bp
    from .blueprints.about.routes import bp as about_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(patients_bp, url_prefix="/patients")
    app.register_blueprint(predict_bp, url_prefix="/predict")
    app.register_blueprint(api_bp, url_prefix="/v1")
    app.register_blueprint(admin_bp)
    app.register_blueprint(fhir_bp, url_prefix="/fhir")
    app.register_blueprint(metrics_bp)
    # Register new feature blueprints
    app.register_blueprint(chatbot_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(about_bp)

    # Health checks
    from .health import bp as health_bp
    app.register_blueprint(health_bp)

    # Error handlers
    from .errors import register_error_handlers
    register_error_handlers(app)

    # CLI
    from .cli import register_cli
    register_cli(app)

    # Demo data seeder (dev convenience; no-op once the DB has any patients)
    from .demo_data import register_seed
    register_seed(app)

    # Lazy first-run schema creation (dev convenience). In production, run
    # `flask init-db` or rely on migrations.
    @app.before_request
    def _ensure_schema():
        try:
            db.session.execute(db.text("SELECT 1 FROM users LIMIT 1"))
        except Exception:
            db.create_all()
        # Always run lightweight additive migrations (cheap when no-op).
        # This is what fixes "no such column: users.area" on dev DBs that
        # pre-date the column being added.
        try:
            from .cli import _apply_light_migrations
            _apply_light_migrations()
        except Exception:
            pass
        try:
            from .seed import seed_default_doctor, seed_doctors
            seed_default_doctor()
            seed_doctors()
        except Exception:
            pass

    return app
