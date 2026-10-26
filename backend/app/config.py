import os
from datetime import timedelta


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me-in-env-file")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-jwt-secret-change-me-in-env-file")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///hosteldesk-dev.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    LOGIN_RATE_LIMIT = "20 per minute"
    TIMERS_ENABLED = os.environ.get("TIMERS_ENABLED", "1") == "1"

    LOGIN_MAX_FAILURES = 5
    LOGIN_FAILURE_WINDOW = timedelta(minutes=15)
    LOGIN_LOCK_DURATION = timedelta(minutes=15)
    PASSWORD_MIN_LENGTH = 12


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    RATELIMIT_ENABLED = False
    TIMERS_ENABLED = False


class ProductionConfig(BaseConfig):
    def __init__(self):
        for key in ("SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"):
            if not os.environ.get(key):
                raise RuntimeError(f"{key} must be set in production")


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
