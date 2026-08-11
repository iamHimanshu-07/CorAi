"""Flask CLI commands."""

from __future__ import annotations

import getpass

import click
from flask import Flask
from flask.cli import with_appcontext
from sqlalchemy import inspect, text

from .extensions import db
from .models import User


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    @with_appcontext
    def init_db():
        """Create all tables, then run lightweight schema migrations."""
        db.create_all()
        _apply_light_migrations()
        click.echo("DB initialized.")

    @app.cli.command("create-user")
    @with_appcontext
    @click.option("--username", required=True)
    @click.option("--role", default="doctor", type=click.Choice(["doctor", "patient", "admin"]))
    @click.option("--email", default=None)
    @click.option("--password", default=None, help="Prompt if omitted")
    @click.option("--area", default=None, help="Area / city (for doctors)")
    def create_user(username: str, role: str, email: str | None, password: str | None, area: str | None):
        """Create a user."""
        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' already exists.")
            return
        pwd = password or getpass.getpass("Password: ")
        user = User(username=username, role=role, email=email, area=area)
        user.set_password(pwd)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created {role} '{username}'.")


def _apply_light_migrations() -> None:
    """Apply non-destructive ALTER TABLE statements for additive columns.

    Use this in dev/demo where adding a column shouldn't require a full
    Alembic migration. New columns go in here.
    """
    db.create_all()
    inspector = inspect(db.engine)
    if "users" in inspector.get_table_names():
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "area" not in user_cols:
            db.session.execute(text("ALTER TABLE users ADD COLUMN area VARCHAR(120)"))
            db.session.commit()
            click.echo("Added users.area column.")
