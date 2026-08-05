"""HDPS application factory."""

from __future__ import annotations

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

    # Blueprints
    from .blueprints.admin.routes import bp as admin_bp
    from .blueprints.api.routes import bp as api_bp
    from .blueprints.auth.routes import bp as auth_bp
    from .blueprints.fhir.routes import bp as fhir_bp
    from .blueprints.main.routes import bp as main_bp
    from .blueprints.metrics.routes import bp as metrics_bp
    from .blueprints.patients.routes import bp as patients_bp
    from .blueprints.predict.routes import bp as predict_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(patients_bp, url_prefix="/patients")
    app.register_blueprint(predict_bp, url_prefix="/predict")
    app.register_blueprint(api_bp, url_prefix="/v1")
    app.register_blueprint(admin_bp)
    app.register_blueprint(fhir_bp, url_prefix="/fhir")
    app.register_blueprint(metrics_bp)

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

    return app
