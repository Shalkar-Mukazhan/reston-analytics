from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "wastecontrol",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.report_tasks", "app.tasks.checklist_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Almaty",
    task_track_started=True,
    beat_schedule={
        # Ночная синхронизация аналитики — 03:00 Алматы
        "nightly-iiko-analytics-sync": {
            "task": "app.tasks.report_tasks.sync_all_iiko_analytics_task",
            "schedule": crontab(hour=3, minute=0),
        },
        # Чек-листы: каждый час → факт из IIKO → Google Sheets
        # В 07:00 Алматы дополнительно: очистка + план
        "checklist-hourly-sync": {
            "task": "app.tasks.checklist_tasks.sync_checklist_hourly",
            "schedule": crontab(minute=0),   # каждый час в 00 минут
        },
        # Планирование: каждый час → sales_daily_facts для ВСЕХ ресторанов
        # Redis-кеш гарантирует отсутствие повторных запросов к IIKO
        "planning-facts-hourly-sync": {
            "task": "app.tasks.checklist_tasks.sync_planning_facts_hourly",
            "schedule": crontab(minute=5),   # в :05 каждого часа (после чек-листа)
        },
    },
)
