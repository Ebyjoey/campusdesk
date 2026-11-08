import logging
import os
import socket

import click
from flask import Flask, jsonify, render_template, request

from .extensions import csrf, db, limiter, login_manager, migrate
from .metrics import init_metrics


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-only-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///campusdesk.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        RATELIMIT_STORAGE_URI="memory://",
        WTF_CSRF_TIME_LIMIT=None,
    )
    if config:
        app.config.update(config)

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    init_metrics(app)

    from . import api, pages

    app.register_blueprint(pages.bp)
    app.register_blueprint(api.bp)

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(error="Authentication required."), 401
        from flask import redirect, url_for

        return redirect(url_for("main.login_page", next=request.path))

    def error_page(code, title):
        def handler(_err):
            if request.path.startswith("/api/"):
                return jsonify(error=title), code
            return render_template("error.html", code=code, title=title), code

        return handler

    app.register_error_handler(403, error_page(403, "Forbidden"))
    app.register_error_handler(404, error_page(404, "Page not found"))
    app.register_error_handler(429, error_page(429, "Too many attempts, slow down"))
    app.register_error_handler(500, error_page(500, "Something went wrong"))

    hostname = socket.gethostname()

    @app.context_processor
    def inject_hostname():
        return {"hostname": hostname}

    register_cli(app)
    return app


DEFAULT_CATEGORIES = [
    ("Hostel", "Hostel Office"),
    ("Mess / Food", "Mess Committee"),
    ("Classroom / Lab", "Academic Office"),
    ("Wi-Fi / Network", "IT Services"),
    ("Electrical / Plumbing", "Maintenance"),
    ("Transport", "Transport Office"),
]


def register_cli(app):
    @app.cli.command("seed")
    @click.option("--password", default=lambda: os.getenv("SEED_PASSWORD", "ChangeMe123!"))
    def seed(password):
        """Create default categories and demo admin/staff/student accounts (idempotent)."""
        from .models import Category, User

        for name, dept in DEFAULT_CATEGORIES:
            if not Category.query.filter_by(name=name).first():
                db.session.add(Category(name=name, default_department=dept))
        demo_users = [
            ("Admin User", "admin@campusdesk.in", "admin"),
            ("Staff One", "staff1@campusdesk.in", "staff"),
            ("Staff Two", "staff2@campusdesk.in", "staff"),
            ("Student Demo", "student@campusdesk.in", "student"),
        ]
        for name, email, role in demo_users:
            if not User.query.filter_by(email=email).first():
                user = User(name=name, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
        db.session.commit()
        click.echo("Seed complete. Demo logins: admin@/staff1@/staff2@/student@campusdesk.in")
