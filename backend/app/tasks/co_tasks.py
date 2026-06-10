"""
Coffee Original — фоновые задачи.
Удаление накладных за предыдущие дни (каждую ночь в 00:00).
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.co_models import CoInvoice

log = logging.getLogger(__name__)

_ALMATY = ZoneInfo("Asia/Almaty")


@celery_app.task(name="app.tasks.co_tasks.purge_old_co_invoices")
def purge_old_co_invoices() -> dict:
    now_almaty = datetime.now(_ALMATY)
    start_of_today = now_almaty.replace(hour=0, minute=0, second=0, microsecond=0)
    db = SessionLocal()
    try:
        rows = (
            db.query(CoInvoice)
            .filter(CoInvoice.created_at < start_of_today)
            .all()
        )
        count = len(rows)
        for inv in rows:
            db.delete(inv)
        db.commit()
        if count:
            log.info("CO purge: удалено %d накладных, загруженных до %s", count, start_of_today.date())
        return {"deleted": count}
    except Exception:
        db.rollback()
        log.exception("CO purge: ошибка при удалении накладных")
        raise
    finally:
        db.close()
