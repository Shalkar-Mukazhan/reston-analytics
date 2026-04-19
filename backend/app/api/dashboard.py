"""
Dashboard API — метрики из waste_metrics.

Логика периода:
- Прошлый месяц: показываем только месячный отчёт (period == "YYYY-MM")
- Текущий месяц: если есть месячный — показываем его,
  иначе — недельные отчёты (period LIKE "YYYY-MM-W%"), по неделям.
"""
from collections import defaultdict
from datetime import datetime, timezone, date as date_type, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.report import Report, ReportItem, WasteMetric
from app.models.restaurant import Restaurant

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _current_ym() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _build_restaurant_metrics(metrics: list[WasteMetric], rest_map: dict) -> list[dict]:
    result = []
    for m in metrics:
        result.append({
            "restaurant_id": m.restaurant_id,
            "restaurant_name": rest_map.get(m.restaurant_id, f"#{m.restaurant_id}"),
            "period": m.period,
            "revenue_sum": m.revenue_sum or 0,
            "shortage_sum": m.shortage_sum or 0,
            "complete_waste_sum": m.complete_waste_sum or 0,
            "shortage_pct": m.shortage_pct or 0,
            "writeoff_pct": m.writeoff_pct or 0,
            "waste_pct": m.waste_pct or 0,
            "to_writeoff_qty": m.to_writeoff_qty or 0,
            "over_limit_count": m.over_limit_count or 0,
            "updated_at": m.created_at,
        })
    result.sort(key=lambda x: x["waste_pct"], reverse=True)
    return result


class RefreshMetricsRequest(BaseModel):
    restaurant_id: int
    period: str   # "YYYY-MM" или "YYYY-MM-WN"


@router.post("/refresh-metrics")
def refresh_metrics(
    body: RefreshMetricsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запускает пересчёт метрик для одного ресторана (Celery, независимо от отчётов)."""
    from app.tasks.report_tasks import refresh_metrics_task
    from fastapi import HTTPException

    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    if current_user.role not in ("admin", "co"):
        allowed = [r.id for r in current_user.restaurants]
        if body.restaurant_id not in allowed:
            raise HTTPException(403, "Нет доступа")

    task = refresh_metrics_task.delay(body.restaurant_id, body.period)
    return {"task_id": task.id, "status": "started"}


@router.post("/refresh-metrics-all")
def refresh_metrics_all(
    period: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Запускает пересчёт метрик для ВСЕХ доступных ресторанов (только CO/admin)."""
    from app.tasks.report_tasks import refresh_metrics_task
    from fastapi import HTTPException

    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Только для CO/admin")

    restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()
    tasks = []
    for r in restaurants:
        task = refresh_metrics_task.delay(r.id, period)
        tasks.append({"restaurant_id": r.id, "task_id": task.id})

    return {"started": len(tasks), "period": period, "tasks": tasks}


@router.get("/")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    month: str = Query(None, description="YYYY-MM, по умолчанию текущий месяц"),
    week: str = Query(None, description="Неделя для текущего месяца, напр. 2026-03-W2"),
):
    if not month:
        month = _current_ym()

    is_current = month == _current_ym()

    # Доступные рестораны
    if current_user.role in ("admin", "co"):
        restaurants = db.query(Restaurant).all()
        rest_ids = [r.id for r in restaurants]
    else:
        restaurants = list(current_user.restaurants)
        rest_ids = [r.id for r in restaurants]

    rest_map = {r.id: r.name for r in restaurants}

    # ── Определяем какие метрики показывать ──────────────────────────────────
    using_weeks = False
    available_weeks: list[str] = []
    selected_week: str | None = None

    # Сначала пробуем месячный отчёт
    monthly_metrics = (
        db.query(WasteMetric)
        .filter(
            WasteMetric.restaurant_id.in_(rest_ids),
            WasteMetric.period == month,
        )
        .all()
    )

    if monthly_metrics:
        # Есть месячный — используем его (и для текущего, и для прошлого)
        metrics = monthly_metrics
    elif is_current:
        # Текущий месяц без месячного → смотрим недели
        using_weeks = True

        # Список доступных недель (уникальные periods вида "YYYY-MM-Wn")
        week_periods = (
            db.query(WasteMetric.period)
            .filter(
                WasteMetric.restaurant_id.in_(rest_ids),
                WasteMetric.period.like(f"{month}-W%"),
            )
            .distinct()
            .order_by(WasteMetric.period)
            .all()
        )
        available_weeks = [row[0] for row in week_periods]

        if available_weeks:
            # Выбранная неделя: из параметра или последняя
            selected_week = week if week in available_weeks else available_weeks[-1]

            metrics = (
                db.query(WasteMetric)
                .filter(
                    WasteMetric.restaurant_id.in_(rest_ids),
                    WasteMetric.period == selected_week,
                )
                .all()
            )
        else:
            metrics = []
    else:
        # Прошлый месяц, нет месячного — пусто (недели не показываем)
        metrics = []

    restaurant_metrics = _build_restaurant_metrics(metrics, rest_map)

    # Summary
    total_revenue  = sum(m["revenue_sum"] for m in restaurant_metrics)
    total_shortage = sum(m["shortage_sum"] for m in restaurant_metrics)
    total_writeoff = sum(m["complete_waste_sum"] for m in restaurant_metrics)
    total_to_writeoff = sum(m["to_writeoff_qty"] for m in restaurant_metrics)
    total_over_limit  = sum(m["over_limit_count"] for m in restaurant_metrics)
    avg_waste_pct = (
        round((total_shortage + total_writeoff) / total_revenue * 100, 2)
        if total_revenue > 0 else 0
    )

    # ── Предыдущий месяц + спарклайн ──────────────────────────────────────────
    y, m_num = map(int, month.split("-"))
    prev_ym = f"{y - 1}-12" if m_num == 1 else f"{y}-{m_num - 1:02d}"

    # Последние 6 месяцев (включая текущий) для спарклайна
    def _prev_periods(ym: str, n: int) -> list[str]:
        result = []
        yr, mo = map(int, ym.split("-"))
        for _ in range(n):
            result.append(f"{yr}-{mo:02d}")
            mo -= 1
            if mo == 0:
                mo, yr = 12, yr - 1
        return list(reversed(result))

    sparkline_periods = _prev_periods(month, 6)

    sparkline_rows = (
        db.query(WasteMetric)
        .filter(
            WasteMetric.restaurant_id.in_(rest_ids),
            WasteMetric.period.in_(sparkline_periods),
            ~WasteMetric.period.like("%-W%"),
        )
        .all()
    ) if rest_ids else []

    # Индексируем по ресторану и периоду
    sparkline_idx: dict[int, dict[str, float]] = defaultdict(dict)
    for row in sparkline_rows:
        sparkline_idx[row.restaurant_id][row.period] = float(row.waste_pct or 0)

    prev_map: dict[int, float] = {
        row.restaurant_id: float(row.waste_pct or 0)
        for row in sparkline_rows
        if row.period == prev_ym
    }

    for rm in restaurant_metrics:
        rid = rm["restaurant_id"]
        prev_pct = prev_map.get(rid)
        rm["prev_month_waste_pct"] = prev_pct
        rm["delta_waste_pct"] = round(rm["waste_pct"] - prev_pct, 2) if prev_pct is not None else None
        rm["sparkline"] = [
            {"period": p, "waste_pct": sparkline_idx[rid].get(p, 0)}
            for p in sparkline_periods
        ]

    # ── Топ-5 проблемных продуктов за период ──────────────────────────────────
    period_filter = selected_week if using_weeks and selected_week else month
    top_products = []
    if rest_ids:
        top_q = (
            db.query(
                ReportItem.product_name,
                func.sum(ReportItem.to_writeoff_qty).label("total_to_writeoff"),
                func.count(func.distinct(Report.restaurant_id)).label("rest_count"),
            )
            .join(Report, ReportItem.report_id == Report.id)
            .filter(
                Report.restaurant_id.in_(rest_ids),
                Report.status == "ready",
                Report.period == period_filter,
                ReportItem.is_over_limit == True,
                ReportItem.product_name.isnot(None),
            )
            .group_by(ReportItem.product_name)
            .order_by(func.sum(ReportItem.to_writeoff_qty).desc())
            .limit(5)
            .all()
        )
        top_products = [
            {
                "product_name": r.product_name,
                "total_to_writeoff": round(float(r.total_to_writeoff or 0), 3),
                "restaurant_count": r.rest_count,
            }
            for r in top_q
        ]

    # ── Отчёты за выбранный период ────────────────────────────────────────────
    recent_reports = (
        db.query(Report, Restaurant)
        .join(Restaurant, Report.restaurant_id == Restaurant.id)
        .filter(
            Report.restaurant_id.in_(rest_ids),
            Report.status == "ready",
            Report.period.like(f"{period_filter}%") if not using_weeks
            else Report.period == period_filter,
        )
        .order_by(Report.created_at.desc())
        .limit(8)
        .all()
    )

    return {
        "current_month": month,
        "is_current": is_current,
        "using_weeks": using_weeks,
        "available_weeks": available_weeks,
        "selected_week": selected_week,
        "summary": {
            "restaurants_count": len(rest_ids),
            "restaurants_with_data": len(restaurant_metrics),
            "total_revenue": round(total_revenue, 2),
            "total_shortage": round(total_shortage, 2),
            "total_writeoff": round(total_writeoff, 2),
            "avg_waste_pct": avg_waste_pct,
            "total_to_writeoff_qty": total_to_writeoff,
            "total_over_limit": total_over_limit,
        },
        "restaurants": restaurant_metrics,
        "top_products": top_products,
        "recent_reports": [
            {
                "id": r.id,
                "restaurant_name": rest.name,
                "period": r.period,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r, rest in recent_reports
        ],
    }


def _map_channel(group: str) -> str:
    g = group.upper()
    if "DLV" in g:
        return "DLV"
    if "DT" in g:
        return "DT"
    if "CAFE" in g:
        return "Cafe"
    if g.startswith("FC"):
        return "FC"
    if "CSO" in g or g.startswith("KZ"):
        return "Kiosk"
    return group


@router.get("/hourly-sales")
def get_hourly_sales(
    restaurant_id: int,
    date: str = Query(None, description="YYYY-MM-DD, по умолчанию сегодня"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Почасовые продажи за день из пресета 'Aim with hour'."""
    from app.services.iiko import fetch_olap
    from app.models.restaurant import PresetDefinition

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    if current_user.role not in ("admin", "co"):
        allowed = [r.id for r in current_user.restaurants]
        if restaurant_id not in allowed:
            raise HTTPException(403, "Нет доступа")

    target_date = date_type.fromisoformat(date) if date else date_type.today()
    # Пресет Aim with hour использует тип DATE — IIKO фильтрует по учётному дню (OpenDate.Typed).
    # Запрашиваем стандартный диапазон T00:00:00, IIKO сам возвращает весь бизнес-день.
    date_from = target_date.strftime("%Y-%m-%dT00:00:00")
    date_to = (target_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    empty = {
        "date": str(target_date),
        "by_channel": [],
        "by_hour": [],
        "totals": {"sales_sum": 0, "gc": 0, "avg_check": 0},
    }

    # Берём пресет: сначала ищем у ресторана, потом глобально
    preset_uuid = restaurant.get_preset("Aim with hour")
    if not preset_uuid:
        preset = db.query(PresetDefinition).filter(
            PresetDefinition.preset_type == "Aim with hour"
        ).first()
        if not preset:
            return empty
        preset_uuid = preset.preset_uuid

    try:
        rows = fetch_olap(db, restaurant, preset_uuid, date_from, date_to)
    except Exception:
        return empty

    # Фильтр по department (OpenDate.Typed фильтруется самим IIKO на стороне сервера)
    dept = restaurant.department_name or restaurant.name
    rows = [r for r in rows if r.get("Department") == dept]

    if not rows:
        return empty

    # Агрегация по каналу + MOP внутри FC
    ch_agg: dict[str, dict] = defaultdict(lambda: {"sales_sum": 0, "gc": 0})
    mop_gc = 0
    mop_sales = 0
    for r in rows:
        ch = _map_channel(r["RestorauntGroup"])
        ch_agg[ch]["sales_sum"] += r["DishDiscountSumInt"]
        ch_agg[ch]["gc"] += r["UniqOrderId"]
        if ch == "FC" and "MOP" in str(r.get("PayTypes", "") or "").upper():
            mop_gc += r["UniqOrderId"]
            mop_sales += r["DishDiscountSumInt"]

    total_sales = sum(v["sales_sum"] for v in ch_agg.values())
    total_gc = sum(v["gc"] for v in ch_agg.values())

    by_channel = []
    for ch, v in sorted(ch_agg.items(), key=lambda x: x[1]["sales_sum"], reverse=True):
        entry = {
            "channel": ch,
            "sales_sum": v["sales_sum"],
            "gc": v["gc"],
            "avg_check": round(v["sales_sum"] / v["gc"]) if v["gc"] > 0 else 0,
            "pct": round(v["sales_sum"] / total_sales * 100, 1) if total_sales > 0 else 0,
            "mop_gc": None,
            "mop_pct": None,
            "mop_sales": None,
            "mop_avg_check": None,
        }
        if ch == "FC" and v["gc"] > 0:
            entry["mop_gc"] = mop_gc
            entry["mop_pct"] = round(mop_gc / v["gc"] * 100, 1)
            entry["mop_sales"] = mop_sales
            entry["mop_avg_check"] = round(mop_sales / mop_gc) if mop_gc > 0 else 0
        by_channel.append(entry)

    # Агрегация по часу
    hr_agg: dict[str, dict] = defaultdict(lambda: {"sales_sum": 0, "gc": 0})
    for r in rows:
        hr_agg[r["HourClose"]]["sales_sum"] += r["DishDiscountSumInt"]
        hr_agg[r["HourClose"]]["gc"] += r["UniqOrderId"]

    start_hour = restaurant.checklist_start_hour or 5

    def _business_hour_key(h):
        try:
            n = int(h)
        except (ValueError, TypeError):
            return 99
        return (n - start_hour) % 24

    by_hour = [
        {
            "hour": h,
            "sales_sum": v["sales_sum"],
            "gc": v["gc"],
            "avg_check": round(v["sales_sum"] / v["gc"]) if v["gc"] > 0 else 0,
        }
        for h, v in sorted(hr_agg.items(), key=lambda x: _business_hour_key(x[0]))
    ]

    return {
        "date": str(target_date),
        "by_channel": by_channel,
        "by_hour": by_hour,
        "totals": {
            "sales_sum": total_sales,
            "gc": total_gc,
            "avg_check": round(total_sales / total_gc) if total_gc > 0 else 0,
        },
    }
