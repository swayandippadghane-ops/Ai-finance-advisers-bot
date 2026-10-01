"""Application configuration.

All secrets (SECRET_KEY, GEMINI_API_KEY) are read from environment variables,
which python-dotenv loads from a local .env file. Nothing secret is hard-coded.
"""
import os
import secrets
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _database_uri():
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    db_path = BASE_DIR / "instance" / "finance.db"
    return "sqlite:///" + db_path.as_posix()


class Config:
    _secret = os.environ.get("SECRET_KEY", "").strip()
    SECRET_KEY = _secret or secrets.token_hex(32)  # random per run if unset
    SECRET_KEY_FROM_ENV = bool(_secret)

    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "").strip() or "gemini-3.5-flash"
    GEMINI_TIMEOUT = 30

    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "").strip() or "\u20b9"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 1024 * 1024
