"""Celery app factory (optional)."""
import os
from celery import Celery

celery = Celery(__name__,
                broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
