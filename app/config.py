"""Configuration classes.

Resolution order:

1. Environment variable (e.g. ``DATABASE_URL``, ``MODEL_PATH``) — set these
   in production to override defaults.
2. Otherwise fall back to repo-local paths (``instance/corai.db``,
   ``models/``, ``.rag_cache/``, ``.hf_cache/``).

The Dockerfile's boot sequence (`flask init-db`) recreates the SQLite DB
on every cold start, so a transient filesystem (like Render's free tier)
is fine.

The SQLite file lives under ``instance/`` rather than the project root
so the parent directory is owned by ``appuser`` and writable at runtime.
Putting it at the project root caused ``sqlite3.OperationalError: unable
to open database file`` on Render because SQLite needs the parent dir to
exist and be writable, and the Dockerfile only chowns ``instance/``,
``models/``, ``.rag_cache/``, ``.hf_cache/``.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _sqlite_uri(path: Path) -> str:
    """Build a SQLAlchemy SQLite URI from an absolute POSIX path.

    Three-slash form (``sqlite:///abs/path``) is correct for an absolute
    filesystem path; four slashes would imply ``localhost`` and a relative
    path. Using ``as_posix()`` keeps the URI forward-slash-separated even
    on Windows where the OS path uses backslashes.
    """
    return f"sqlite:///{path.as_posix()}"


class Config:
    """Base config."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Local SQLite by default; override with DATABASE_URL in production.
    # Stored under instance/ so the parent dir is reliably writable on
    # Render free tier (chown'd to appuser in the Dockerfile).
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        _sqlite_uri(BASE_DIR / "instance" / "corai.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Model artifact path; default lives next to the source.
    MODEL_PATH = os.getenv(
        "MODEL_PATH",
        str(BASE_DIR / "models" / "corai-1.0.0.pkl"),
    )
    MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")

    # Sessions
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours
    SESSION_COOKIE_SECURE = bool(int(os.getenv("SESSION_COOKIE_SECURE", "0")))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # CSRF
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 4

    # Rate limiting
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_DEFAULT = "200 per hour"

    # Map tile URL (Leaflet with OpenStreetMap free tiles)
    MAP_TILE_URL = os.getenv("MAP_TILE_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")
    # PDF upload settings
    PDF_MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MiB max upload size
    ALLOWED_EXTENSIONS = {"pdf"}
    # About Us source URL (e.g., WHO health page)
    ABOUT_US_SOURCE_URL = os.getenv("ABOUT_US_SOURCE_URL", "https://www.who.int/news-room")

    # Bootstrap admin (seeded on first request if missing)
    BOOTSTRAP_DOCTOR_USERNAME = os.getenv("BOOTSTRAP_DOCTOR_USERNAME", "doctor")
    BOOTSTRAP_DOCTOR_PASSWORD = os.getenv("BOOTSTRAP_DOCTOR_PASSWORD", "doctor123")
    BOOTSTRAP_DOCTOR_EMAIL = os.getenv("BOOTSTRAP_DOCTOR_EMAIL", "doctor@corai.local")
    BOOTSTRAP_DOCTOR_AREA = os.getenv("BOOTSTRAP_DOCTOR_AREA", "India")
    BOOTSTRAP_ADMIN_USERNAME = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
    BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "admin123")
    BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@corai.local")
    BOOTSTRAP_ADMIN_AREA = os.getenv("BOOTSTRAP_ADMIN_AREA", "India")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    RATELIMIT_ENABLED = False
    BOOTSTRAP_DOCTOR_PASSWORD = "test-password"
