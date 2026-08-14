"""Configuration classes.

Resolution order:

1. Environment variable (e.g. ``DATABASE_URL``, ``MODEL_PATH``) — set these
   in production to override defaults.
2. Otherwise fall back to repo-local paths (``corai.db``, ``models/``,
   ``.rag_cache/``, ``.hf_cache/``).

The Dockerfile's boot sequence (`flask init-db` + `python -m ml.train`)
recreates the SQLite DB and model artifact on every cold start, so a
transient filesystem (like Render's free tier) is fine.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _sqlite_uri(path: Path) -> str:
    """Build a SQLAlchemy SQLite URI from an absolute POSIX path."""
    return f"sqlite:///{path.as_posix()}"


class Config:
    """Base config."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Local SQLite by default; override with DATABASE_URL in production.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        _sqlite_uri(BASE_DIR / "corai.db"),
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

    # RAG engine — both env names are accepted (legacy + current).
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
    # LLM (OpenAI) key for the chatbot fallback path.
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
    # Map tile URL (Leaflet with OpenStreetMap free tiles)
    MAP_TILE_URL = os.getenv("MAP_TILE_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png")
    # PDF upload settings
    PDF_MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MiB max upload size
    ALLOWED_EXTENSIONS = {"pdf"}
    # About Us source URL (e.g., WHO health page)
    ABOUT_US_SOURCE_URL = os.getenv("ABOUT_US_SOURCE_URL", "https://www.who.int/news-room")

    # Bootstrap admin (seeded on first request if missing)
    BOOTSTRAP_DOCTOR_USERNAME = os.getenv("BOOTSTRAP_DOCTOR_USERNAME", "doctor")
    BOOTSTRAP_DOCTOR_PASSWORD = os.getenv("BOOTSTRAP_DOCTOR_PASSWORD", "corai2026")
    BOOTSTRAP_DOCTOR_EMAIL = os.getenv("BOOTSTRAP_DOCTOR_EMAIL", "doctor@corai.local")
    BOOTSTRAP_DOCTOR_AREA = os.getenv("BOOTSTRAP_DOCTOR_AREA", "India")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    RATELIMIT_ENABLED = False
    BOOTSTRAP_DOCTOR_PASSWORD = "test-password"
