import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    db_path = INSTANCE_DIR / "app.db"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "postgresql://patnametro_user:hIdIg3WDwkQa1X8zC1xZBy11lbtlH5lc@dpg-d7gd5ui8qa3s73do5gu0-a/patnametro",
        f"sqlite:///{db_path.as_posix()}"
    )

    if SQLALCHEMY_DATABASE_URI.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://",
            "postgresql://",
            1
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # Redis / SocketIO
    REDIS_URL = os.environ.get("REDIS_URL", "")
    SOCKETIO_MESSAGE_QUEUE = REDIS_URL or None

    # Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    WTF_CSRF_TIME_LIMIT = None

    # Rate limit storage
    RATELIMIT_STORAGE_URI = REDIS_URL or "memory://"

    # Payments
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
    CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "")
    CASHFREE_SECRET = os.environ.get("CASHFREE_SECRET", "")

    # Admin bootstrap
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@local.test")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Admin@12345")
    ADMIN_MOBILE = os.environ.get("ADMIN_MOBILE", "9999999999")

    # OTP (dev: printed to console; integrate SMS provider in prod)
    OTP_TTL_SECONDS = 300
    OTP_DEV_PRINT = True

    # Game economy
    DEFAULT_RTP = float(os.environ.get("DEFAULT_RTP", "0.90"))
    MIN_DEPOSIT = 10
    MIN_WITHDRAW = 100
    WITHDRAW_COOLDOWN_MINUTES = 30
