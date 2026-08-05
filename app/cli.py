"""Flask CLI commands."""

from __future__ import annotations

import getpass

import click
from flask import Flask
from flask.cli import with_appcontext

from .extensions import db
from .models import User


def register_cli(app: Flask) -> None:
    @app.cli.command("init-db")
    @with_appcontext
    def init_db():
        """Create all tables."""
        db.create_all()
        click.echo("DB initialized.")

    @app.cli.command("create-user")
    @with_appcontext
    @click.option("--username", required=True)
    @click.option("--role", default="doctor", type=click.Choice(["doctor", "patient", "admin"]))
    @click.option("--email", default=None)
    @click.option("--password", default=None, help="Prompt if omitted")
    def create_user(username: str, role: str, email: str | None, password: str | None):
        """Create a user."""
        if User.query.filter_by(username=username).first():
            click.echo(f"User '{username}' already exists.")
            return
        pwd = password or getpass.getpass("Password: ")
        user = User(username=username, role=role, email=email)
        user.set_password(pwd)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created {role} '{username}'.")
