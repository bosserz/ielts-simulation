import os


def _fix_db_url(url: str) -> str:
    # Render (and Heroku) provide postgres:// but SQLAlchemy requires postgresql://
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get("DATABASE_URL", "sqlite:///dev.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "ielts-media")
    R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL", "")

    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # GCP Cloud Speech-to-Text — store the service account JSON content as a string
    GCP_SERVICE_ACCOUNT_JSON = os.environ.get("GCP_SERVICE_ACCOUNT_JSON", "")

    SENTRY_DSN = os.environ.get("SENTRY_DSN", "")

    # Exam session lock: max one active session per student
    MAX_ACTIVE_SESSIONS_PER_USER = 1

    # IndexedDB sync heartbeat interval (seconds) — must match timer.js
    SESSION_HEARTBEAT_INTERVAL = 60


class DevelopmentConfig(Config):
    DEBUG = True
    WTF_CSRF_ENABLED = False  # disable CSRF in dev for easier API testing


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
