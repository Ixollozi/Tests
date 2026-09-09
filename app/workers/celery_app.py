from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "medicalka",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "cleanup-unverified-users-hourly": {
            "task": "app.workers.tasks.cleanup_unverified_users_task",
            "schedule": crontab(minute=0),
        },
    },
)
