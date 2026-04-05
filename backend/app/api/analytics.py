"""
Analytics API — динамика по месяцам из waste_metrics.
Только месячные периоды (не недельные).
"""
import calendar
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user, require_co
from app.models.user import User
from app.models.report import Report, ReportItem, WasteMetric
from app.models.restaurant import Restaurant
from app.models.catalog import ProductCatalog, ProductGroup
from app.services.iiko import fetch_olap
import pandas as pd

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

WASTE_LIMIT = 0.3


def _accessible_rest_ids(current_user: User, db: Session) -> list[int]:
    if current_user.role in ("admin", "co"):
        return [r.id for r in db.query(Restaurant).filter(Restaurant.is_active == True).all()]
    return [r.id for r in current_user.restaurants]


@router.get("/restaurants")
def list_analytics_restaurants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список ресторанов доступных пользователю (для селектора)."""
    if current_user.role in ("admin", "co"):
        rests = db.query(Restaurant).filter(Restaurant.is_active == True).order_by(Restaurant.name).all()
    else:
        rests = list(current_user.restaurants)
    return [{"id": r.id, "name": r.name, "code": r.code} for r in rests]


@router.get("/yearly")
def get_yearly(
    year: int = Query(..., description="Год, напр. 2026"),
    restaurant_id: Optional[int] = Query(None, description="ID ресторана; если не задан — агрегат по всем"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Возвращает 12 месяцев данных за год.
    Только месячные периоды (без -W).
    """
    accessible = _accessible_rest_ids(current_user, db)

    if restaurant_id:
        if restaurant_id not in accessible:
            return {"year": year, "months": _empty_year(year), "restaurant_id": restaurant_id}
        rest_ids = [restaurant_id]
    else:
        rest_ids = accessible

    # Агрегируем по периоду (может быть несколько ресторанов)
    rows = (
        db.query(
            WasteMetric.period,
            func.sum(WasteMetric.revenue_sum).label("revenue_sum"),
            func.sum(WasteMetric.shortage_sum).label("shortage_sum"),
            func.sum(WasteMetric.complete_waste_sum).label("complete_waste_sum"),
            func.sum(WasteMetric.to_writeoff_qty).label("to_writeoff_qty"),
            func.sum(WasteMetric.over_limit_count).label("over_limit_count"),
        )
        .filter(
            WasteMetric.restaurant_id.in_(rest_ids),
            WasteMetric.period.like(f"{year}-%"),
            ~WasteMetric.period.like(f"{year}-%-W%"),  # исключаем недельные
        )
        .group_by(WasteMetric.period)
        .order_by(WasteMetric.period)
        .all()
    )

    # Индексируем по номеру месяца
    by_month: dict[int, dict] = {}
    for row in rows:
        month_num = int(row.period.split("-")[1])
        rev = float(row.revenue_sum or 0)
        sho = float(row.shortage_sum or 0)
        wri = float(row.complete_waste_sum or 0)
        by_month[month_num] = {
            "revenue_sum": round(rev, 2),
            "shortage_sum": round(sho, 2),
            "complete_waste_sum": round(wri, 2),
            "shortage_pct": round(sho / rev * 100, 4) if rev > 0 else 0,
            "writeoff_pct": round(wri / rev * 100, 4) if rev > 0 else 0,
            "waste_pct": round((sho + wri) / rev * 100, 4) if rev > 0 else 0,
            "over_limit_count": int(row.over_limit_count or 0),
            "to_writeoff_qty": float(row.to_writeoff_qty or 0),
        }

    month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                   "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]

    months = []
    for mn in range(1, 13):
        d = by_month.get(mn, {})
        months.append({
            "month": mn,
            "month_name": month_names[mn - 1],
            "period": f"{year}-{mn:02d}",
            "has_data": mn in by_month,
            "revenue_sum": d.get("revenue_sum", 0),
            "shortage_sum": d.get("shortage_sum", 0),
            "complete_waste_sum": d.get("complete_waste_sum", 0),
            "shortage_pct": d.get("shortage_pct", 0),
            "writeoff_pct": d.get("writeoff_pct", 0),
            "waste_pct": d.get("waste_pct", 0),
            "over_limit_count": d.get("over_limit_count", 0),
            "to_writeoff_qty": d.get("to_writeoff_qty", 0),
            "waste_limit": WASTE_LIMIT,
        })

    # Годовые итоги
    with_data = [m for m in months if m["has_data"]]
    total_rev = sum(m["revenue_sum"] for m in with_data)
    total_sho = sum(m["shortage_sum"] for m in with_data)
    total_wri = sum(m["complete_waste_sum"] for m in with_data)
    avg_waste = round((total_sho + total_wri) / total_rev * 100, 2) if total_rev > 0 else 0

    return {
        "year": year,
        "restaurant_id": restaurant_id,
        "totals": {
            "revenue_sum": round(total_rev, 2),
            "shortage_sum": round(total_sho, 2),
            "complete_waste_sum": round(total_wri, 2),
            "avg_waste_pct": avg_waste,
            "months_with_data": len(with_data),
        },
        "months": months,
    }


@router.get("/over-limit")
def get_over_limit(
    year: int = Query(...),
    restaurant_id: Optional[int] = Query(None),
    limit: int = Query(15),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Топ групп и топ продуктов, которые превышали норму в выбранном году.
    Только месячные периоды.
    """
    accessible = _accessible_rest_ids(current_user, db)
    if restaurant_id:
        rest_ids = [restaurant_id] if restaurant_id in accessible else []
    else:
        rest_ids = accessible

    # Фильтр: отчёты за год, только месячные периоды
    year_prefix = f"{year}-%"

    base_q = (
        db.query(ReportItem)
        .join(Report, ReportItem.report_id == Report.id)
        .filter(
            Report.restaurant_id.in_(rest_ids),
            Report.status == "ready",
            Report.period.like(year_prefix),
            ~Report.period.like(f"{year}-%-W%"),
            ReportItem.is_over_limit == True,
        )
    )

    items = (
        base_q
        .join(ProductCatalog, ReportItem.product_id == ProductCatalog.id, isouter=True)
        .join(ProductGroup, ProductCatalog.group_id == ProductGroup.id, isouter=True)
        .with_entities(
            ReportItem.id,
            ProductCatalog.name.label("product_name"),
            ProductGroup.name.label("group_name"),
            ReportItem.sales_qty,
            ReportItem.writeoff_qty,
            ReportItem.allowed_qty,
            ReportItem.to_writeoff_qty,
            ReportItem.written_off_pct,
            Report.period,
        )
        .all()
    )

    # Агрегация по группам
    group_agg: dict[str, dict] = {}
    for row in items:
        gname = row.group_name or "Без группы"
        if gname not in group_agg:
            group_agg[gname] = {
                "group_name": gname,
                "occurrences": 0,
                "total_to_writeoff": 0.0,
                "total_writeoff_qty": 0.0,
                "total_allowed_qty": 0.0,
                "total_sales_qty": 0.0,
            }
        g = group_agg[gname]
        g["occurrences"] += 1
        g["total_to_writeoff"] += float(row.to_writeoff_qty or 0)
        g["total_writeoff_qty"] += float(row.writeoff_qty or 0)
        g["total_allowed_qty"] += float(row.allowed_qty or 0)
        g["total_sales_qty"] += float(row.sales_qty or 0)

    top_groups = sorted(
        group_agg.values(), key=lambda x: x["total_to_writeoff"], reverse=True
    )[:limit]
    for g in top_groups:
        g["total_to_writeoff"] = round(g["total_to_writeoff"], 3)
        g["total_writeoff_qty"] = round(g["total_writeoff_qty"], 3)
        g["total_allowed_qty"] = round(g["total_allowed_qty"], 3)

    # Агрегация по продуктам
    prod_agg: dict[str, dict] = {}
    for row in items:
        pname = row.product_name or "Неизвестный товар"
        gname = row.group_name or "—"
        key = f"{pname}||{gname}"
        if key not in prod_agg:
            prod_agg[key] = {
                "product_name": pname,
                "group_name": gname,
                "occurrences": 0,
                "total_to_writeoff": 0.0,
                "total_writeoff_qty": 0.0,
                "total_allowed_qty": 0.0,
            }
        p = prod_agg[key]
        p["occurrences"] += 1
        p["total_to_writeoff"] += float(row.to_writeoff_qty or 0)
        p["total_writeoff_qty"] += float(row.writeoff_qty or 0)
        p["total_allowed_qty"] += float(row.allowed_qty or 0)

    top_products = sorted(
        prod_agg.values(), key=lambda x: x["total_to_writeoff"], reverse=True
    )[:limit]
    for p in top_products:
        p["total_to_writeoff"] = round(p["total_to_writeoff"], 3)
        p["total_writeoff_qty"] = round(p["total_writeoff_qty"], 3)
        p["total_allowed_qty"] = round(p["total_allowed_qty"], 3)

    return {
        "year": year,
        "total_over_limit_records": len(items),
        "top_groups": top_groups,
        "top_products": top_products,
    }


def _empty_year(year: int) -> list:
    month_names = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                   "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
    return [
        {
            "month": mn, "month_name": month_names[mn - 1],
            "period": f"{year}-{mn:02d}", "has_data": False,
            "revenue_sum": 0, "shortage_sum": 0, "complete_waste_sum": 0,
            "shortage_pct": 0, "writeoff_pct": 0, "waste_pct": 0,
            "over_limit_count": 0, "to_writeoff_qty": 0, "waste_limit": WASTE_LIMIT,
        }
        for mn in range(1, 13)
    ]


@router.post("/sync-iiko")
def sync_analytics_from_iiko(
    restaurant_id: int = Query(..., description="ID ресторана"),
    year: int = Query(..., description="Год, напр. 2026"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Запускает синхронизацию из IIKO через Celery (асинхронно).
    Возвращает task_id — статус можно проверить через GET /analytics/task-status/{task_id}.
    """
    from app.tasks.report_tasks import sync_iiko_analytics_task

    accessible = _accessible_rest_ids(current_user, db)
    if restaurant_id not in accessible:
        raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    revenue_preset = restaurant.get_preset("revenue_net")
    waste_preset = restaurant.get_preset("complete_waste")
    if not revenue_preset and not waste_preset:
        raise HTTPException(
            status_code=422,
            detail="У ресторана нет пресетов revenue_net и complete_waste. Настройте их в Администрировании."
        )

    task = sync_iiko_analytics_task.delay(restaurant_id, year)
    return {"task_id": task.id, "status": "started"}


@router.get("/task-status/{task_id}")
def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Статус Celery-задачи синхронизации из IIKO."""
    from celery.result import AsyncResult
    from app.tasks.celery_app import celery_app as _app

    result = AsyncResult(task_id, app=_app)
    if result.ready():
        return {"task_id": task_id, "status": "done", "result": result.result}
    return {"task_id": task_id, "status": result.state.lower(), "result": None}
