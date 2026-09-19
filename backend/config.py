import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root; real environment variables take precedence
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _split_csv(value: str) -> list[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


DATABASE_URL = os.getenv(
    "DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/student_db"
)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
CORS_ORIGINS = _split_csv(os.getenv("CORS_ORIGINS", ""))

# Session cookie: must be true in production behind HTTPS
COOKIE_NAME = "sms_session"
COOKIE_SECURE = _bool(os.getenv("COOKIE_SECURE", "false"))

# Login rate limit: lock a username / IP for M minutes after N consecutive failures
LOGIN_MAX_FAILURES = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
LOGIN_LOCK_MINUTES = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))

# Set to true behind a reverse proxy (nginx / Caddy) to read the real IP from X-Forwarded-For
TRUST_PROXY = _bool(os.getenv("TRUST_PROXY", "false"))
