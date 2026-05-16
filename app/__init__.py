import os
from flask import Flask, redirect, url_for
from flask_login import current_user
from .config import config_map
from .extensions import db, login_manager, migrate, csrf


def create_app(config_name: str | None = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Import models so Flask-Migrate sees them
    with app.app_context():
        from .models import user, exam, session, response, score, annotation, report  # noqa: F401

    # Register blueprints
    from .blueprints.auth import auth_bp
    from .blueprints.student import student_bp
    from .blueprints.exam import exam_bp
    from .blueprints.admin import admin_bp
    from .blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(exam_bp)
    app.register_blueprint(admin_bp)
    csrf.exempt(api_bp)
    app.register_blueprint(api_bp)

    # Register CLI commands
    from .commands import (
        seed_mock_command, seed_mock2_command, seed_mock3_command,
        seed_mock4_command, seed_teacher_command, create_admin_command,
        rescore_objective_command,
    )
    app.cli.add_command(seed_mock_command)
    app.cli.add_command(seed_mock2_command)
    app.cli.add_command(seed_mock3_command)
    app.cli.add_command(seed_mock4_command)
    app.cli.add_command(seed_teacher_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(rescore_objective_command)

    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("admin.dashboard" if current_user.is_teacher else "student.dashboard"))
        return redirect(url_for("auth.login"))

    # Sentry error tracking (no-op if DSN is empty)
    if app.config.get("SENTRY_DSN"):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        sentry_sdk.init(dsn=app.config["SENTRY_DSN"], integrations=[FlaskIntegration()])

    return app
