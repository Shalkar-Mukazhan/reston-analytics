from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "wastecontrol",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.co_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Almaty",
    task_track_started=True,
    beat_schedule={
        # CO: удаление накладных за предыдущие дни — каждый день в 00:00
        "co-purge-old-invoices": {
            "task": "app.tasks.co_tasks.purge_old_co_invoices",
            "schedule": crontab(hour=0, minute=0),
        },
    },
)
