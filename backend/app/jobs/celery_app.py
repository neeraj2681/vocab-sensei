"""The Celery application (without a configured broker it uses an in-memory one, never used)."""

from celery import Celery

from app.core.config import get_settings

celery_app = Celery(
    "vocab_sensei",
    broker=get_settings().jobs.broker_url or "memory://",
    include=["app.jobs.tasks"],
)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    task_time_limit=1800,
    task_soft_time_limit=1700,
)
