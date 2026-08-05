"""Configuration classes."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    """Base config."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'hdps.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Model
    MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "models" / "hdps-1.0.0.pkl"))
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

    # Gemini (reserved for future use; not consumed by 1.0.0)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    # Bootstrap admin (seeded on first request if missing)
    BOOTSTRAP_DOCTOR_USERNAME = os.getenv("BOOTSTRAP_DOCTOR_USERNAME", "doctor")
    BOOTSTRAP_DOCTOR_PASSWORD = os.getenv("BOOTSTRAP_DOCTOR_PASSWORD", "hdps2026")
    BOOTSTRAP_DOCTOR_EMAIL = os.getenv("BOOTSTRAP_DOCTOR_EMAIL", "doctor@hdps.local")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "test-secret"
    RATELIMIT_ENABLED = False
    BOOTSTRAP_DOCTOR_PASSWORD = "test-password"
