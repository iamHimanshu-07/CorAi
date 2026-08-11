"""Configuration classes.

Resolution order for data paths (so the same image runs locally AND on a
hosted PaaS without code changes):

1. Environment variable (e.g. ``DATABASE_URL``, ``MODEL_PATH``). On Render
   / Railway / Fly / etc. point these at the persistent disk, e.g.
   ``MODEL_PATH=/data/models/corai-1.0.0.pkl``.
2. If ``/data`` is writable (always on Render with a disk, always on
   Railway with a volume), default to ``/data`` for the SQLite DB, model
   artifact, RAG cache, and HF cache.
3. Otherwise (local dev, CI, tests) fall back to the repo-root paths.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# /data is the conventional mount for a persistent volume on Render
# (disks) and Railway (volumes). If it exists AND is writable, use it.
_DATA_DIR = Path(os.getenv("CorAi_DATA_DIR", "/data"))
_HAS_PERSISTENT = _DATA_DIR.exists() and os.access(_DATA_DIR, os.W_OK)
_PERSIST_PREFIX = _DATA_DIR if _HAS_PERSISTENT else BASE_DIR


def _sqlite_uri(path: Path) -> str:
    """Build a SQLAlchemy SQLite URI from an absolute POSIX path."""
    return f"sqlite:///{path.as_posix()}"


class Config:
    """Base config."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")

    # Default DB to the persistent volume if we have one, else repo root.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        _sqlite_uri(_PERSIST_PREFIX / "corai.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Model artifact — same idea: persistent volume if available.
    MODEL_PATH = os.getenv(
        "MODEL_PATH",
        str(_PERSIST_PREFIX / "models" / "corai-1.0.0.pkl"),
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
