"""
Planning API — месячные цели + дневные планы/факты продаж.

Логика:
- Факты берутся из sales_daily_facts (синхр. из IIKO через 'Aim with hour' пресет)
- Планы генерируются из исторических фактов: взвешенное среднее 8 последних таких же дней недели
- Цели ставит CO/admin вручную в sales_monthly_targets
"""
import calendar
from datetime import date, timedelta, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.restaurant import Restaurant, PresetDefinition
from app.models.planning import SalesMonthlyTarget, SalesDailyFact, SalesDailyPlan

router = APIRouter(prefix="/api/planning", tags=["planning"])

# Казахстанские праздники 2025–2027
KZ_HOLIDAYS = {
    date(2025, 1, 1), date(2025, 1, 2), date(2025, 3, 8),
    date(2025, 3, 21), date(2025, 3, 22), date(2025, 3, 23),
    date(2025, 5, 1), date(2025, 5, 7), date(2025, 5, 9),
    date(2025, 7, 6), date(2025, 8, 30), date(2025, 12, 1),
    date(2025, 12, 16), date(2025, 12, 17),
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 3, 8),
    date(2026, 3, 21), date(2026, 3, 22), date(2026, 3, 23),
    date(2026, 5, 1), date(2026, 5, 7), date(2026, 5, 9),
    date(2026, 7, 6), date(2026, 8, 30), date(2026, 12, 1),
    date(2026, 12, 16), date(2026, 12, 17),
    date(2027, 1, 1), date(2027, 1, 2),
}

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def _get_restaurant(db: Session, restaurant_id: int, user: User) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")
    if user.role not in ("admin", "co"):
        allowed = [r.id for r in user.restaurants]
        if restaurant_id not in allowed:
            raise HTTPException(403, "Нет доступа")
    return restaurant


def _sync_facts_from_iiko(db: Session, restaurant: Restaurant, date_from: date, date_to: date):
    """Загружает факты из IIKO за диапазон дат и сохраняет в sales_daily_facts."""
    from app.services.iiko import fetch_olap

    preset_uuid = restaurant.get_preset("Aim with hour")
    if not preset_uuid:
        preset = db.query(PresetDefinition).filter(
            PresetDefinition.preset_type == "Aim with hour"
        ).first()
        if not preset:
            return 0
        preset_uuid = preset.preset_uuid

    iiko_from = date_from.strftime("%Y-%m-%dT00:00:00")
    iiko_to = (date_to + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    try:
        rows = fetch_olap(db, restaurant, preset_uuid, iiko_from, iiko_to)
    except Exception:
        return 0

    dept = restaurant.department_name or restaurant.name
    rows = [r for r in rows if r.get("Department") == dept]
    if not rows:
        return 0

    # Группируем по дате
    from collections import defaultdict
    by_date: dict[str, dict] = defaultdict(lambda: {"gc": 0, "sales": 0})
    for r in rows:
        d_str = r.get("OpenDate.Typed", "")[:10]
        if not d_str:
            continue
        by_date[d_str]["gc"] += r.get("UniqOrderId", 0)
        by_date[d_str]["sales"] += r.get("DishDiscountSumInt", 0)

    saved = 0
    for d_str, v in by_date.items():
        try:
            d = date.fromisoformat(d_str)
        except ValueError:
            continue
        gc = v["gc"]
        sales = v["sales"]
        av_check = round(sales / gc, 2) if gc > 0 else 0

        existing = db.query(SalesDailyFact).filter(
            SalesDailyFact.restaurant_id == restaurant.id,
            SalesDailyFact.date == d,
        ).first()
        if existing:
            existing.gc_fact = gc
            existing.sales_fact = sales
            existing.av_check_fact = av_check
            existing.synced_at = datetime.now(timezone.utc)
        else:
            db.add(SalesDailyFact(
                restaurant_id=restaurant.id,
                date=d,
                gc_fact=gc,
                sales_fact=sales,
                av_check_fact=av_check,
            ))
        saved += 1

    db.commit()
    return saved


def _generate_plans(db: Session, restaurant_id: int, from_date: date, days_ahead: int = 35):
    """Генерирует планы на N дней вперёд по взвешенному среднему."""
    weights = [8, 7, 6, 5, 4, 3, 2, 1]

    facts = db.query(SalesDailyFact).filter(
        SalesDailyFact.restaurant_id == restaurant_id,
        SalesDailyFact.date < from_date,
        SalesDailyFact.gc_fact > 0,
    ).all()

    facts_by_date = {f.date: f for f in facts}

    generated = 0
    for i in range(days_ahead):
        target = from_date + timedelta(days=i)
        target_wd = target.weekday()

        # Последние 8 дат с тем же днём недели, не праздник
        same_wd = sorted(
            [f for d, f in facts_by_date.items()
             if d.weekday() == target_wd and d not in KZ_HOLIDAYS],
            key=lambda f: f.date,
            reverse=True,
        )[:8]

        if not same_wd:
            continue

        w = weights[:len(same_wd)]
        total_w = sum(w)
        gc_plan = round(sum(f.gc_fact * w[j] for j, f in enumerate(same_wd)) / total_w)
        sales_plan = round(sum(float(f.sales_fact) * w[j] for j, f in enumerate(same_wd)) / total_w, 2)
        av_check_plan = round(sales_plan / gc_plan, 2) if gc_plan > 0 else 0

        existing = db.query(SalesDailyPlan).filter(
            SalesDailyPlan.restaurant_id == restaurant_id,
            SalesDailyPlan.date == target,
        ).first()
        if existing:
            # Не перезаписываем вручную заданные значения
            if existing.is_manual:
                continue
            existing.gc_plan = gc_plan
            existing.sales_plan = sales_plan
            existing.av_check_plan = av_check_plan
        else:
            db.add(SalesDailyPlan(
                restaurant_id=restaurant_id,
                date=target,
                gc_plan=gc_plan,
                sales_plan=sales_plan,
                av_check_plan=av_check_plan,
                is_manual=False,
            ))
        generated += 1

    db.commit()
    return generated


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/")
def get_planning(
    restaurant_id: int,
    month: str = Query(None, description="YYYY-MM, по умолчанию текущий"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Возвращает цель, факт и планы по дням для выбранного месяца."""
    restaurant = _get_restaurant(db, restaurant_id, current_user)

    if not month:
        month = date.today().strftime("%Y-%m")

    year, mon = map(int, month.split("-"))
    first_day = date(year, mon, 1)
    last_day = date(year, mon, calendar.monthrange(year, mon)[1])

    # Месячная цель
    target = db.query(SalesMonthlyTarget).filter(
        SalesMonthlyTarget.restaurant_id == restaurant_id,
        SalesMonthlyTarget.month == month,
    ).first()

    # Факты за месяц
    facts = db.query(SalesDailyFact).filter(
        SalesDailyFact.restaurant_id == restaurant_id,
        SalesDailyFact.date >= first_day,
        SalesDailyFact.date <= last_day,
    ).all()
    facts_map = {f.date: f for f in facts}

    # Планы за месяц
    plans = db.query(SalesDailyPlan).filter(
        SalesDailyPlan.restaurant_id == restaurant_id,
        SalesDailyPlan.date >= first_day,
        SalesDailyPlan.date <= last_day,
    ).all()
    plans_map = {p.date: p for p in plans}

    # Строим таблицу по дням
    days = []
    today = date.today()
    for i in range((last_day - first_day).days + 1):
        d = first_day + timedelta(days=i)
        fact = facts_map.get(d)
        plan = plans_map.get(d)
        is_holiday = d in KZ_HOLIDAYS

        pct_done = None
        if plan and plan.sales_plan and fact and fact.sales_fact:
            pct_done = round(float(fact.sales_fact) / float(plan.sales_plan) * 100, 1)

        days.append({
            "date": d.isoformat(),
            "weekday": WEEKDAYS_RU[d.weekday()],
            "is_today": d == today,
            "is_future": d > today,
            "is_holiday": is_holiday,
            "gc_plan": plan.gc_plan if plan else None,
            "sales_plan": float(plan.sales_plan) if plan and plan.sales_plan else None,
            "av_check_plan": float(plan.av_check_plan) if plan and plan.av_check_plan else None,
            "is_manual": plan.is_manual if plan else False,
            "gc_fact": fact.gc_fact if fact else None,
            "sales_fact": float(fact.sales_fact) if fact and fact.sales_fact else None,
            "av_check_fact": float(fact.av_check_fact) if fact and fact.av_check_fact else None,
            "pct_done": pct_done,
        })

    # Итоги факта за месяц
    fact_sales_sum = sum(float(f.sales_fact) for f in facts if f.sales_fact)
    fact_gc_sum = sum(f.gc_fact for f in facts if f.gc_fact)
    plan_sales_sum = sum(float(p.sales_plan) for p in plans if p.sales_plan)

    return {
        "month": month,
        "restaurant_name": restaurant.name,
        "target": {
            "gc_target": target.gc_target if target else None,
            "sales_target": float(target.sales_target) if target and target.sales_target else None,
        },
        "fact_totals": {
            "sales_sum": round(fact_sales_sum, 2),
            "gc_sum": fact_gc_sum,
            "av_check": round(fact_sales_sum / fact_gc_sum, 2) if fact_gc_sum else 0,
        },
        "plan_totals": {
            "sales_sum": round(plan_sales_sum, 2),
        },
        "pct_of_target": round(fact_sales_sum / float(target.sales_target) * 100, 1)
            if target and target.sales_target else None,
        "days": days,
        "has_facts": len(facts) > 0,
        "has_plans": len(plans) > 0,
    }


class SetTargetRequest(BaseModel):
    restaurant_id: int
    month: str
    gc_target: Optional[int] = None
    sales_target: Optional[float] = None


@router.put("/monthly-target")
def set_monthly_target(
    body: SetTargetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Только для CO/admin")

    existing = db.query(SalesMonthlyTarget).filter(
        SalesMonthlyTarget.restaurant_id == body.restaurant_id,
        SalesMonthlyTarget.month == body.month,
    ).first()

    if existing:
        existing.gc_target = body.gc_target
        existing.sales_target = body.sales_target
        existing.set_by = current_user.id
    else:
        db.add(SalesMonthlyTarget(
            restaurant_id=body.restaurant_id,
            month=body.month,
            gc_target=body.gc_target,
            sales_target=body.sales_target,
            set_by=current_user.id,
        ))
    db.commit()
    return {"ok": True}


@router.post("/sync-history")
def sync_history(
    restaurant_id: int,
    months: int = Query(3, ge=1, le=12),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Загружает исторические данные из IIKO (месяц за месяцем) и генерирует планы."""
    restaurant = _get_restaurant(db, restaurant_id, current_user)
    today = date.today()
    total_saved = 0

    # Синхронизируем по месяцам назад
    for i in range(months):
        # i=0 → текущий месяц, i=1 → прошлый, ...
        yr = today.year
        mo = today.month - i
        while mo <= 0:
            mo += 12
            yr -= 1
        first = date(yr, mo, 1)
        last = date(yr, mo, calendar.monthrange(yr, mo)[1])
        # Не уходим в будущее
        if first > today:
            continue
        if last > today:
            last = today

        saved = _sync_facts_from_iiko(db, restaurant, first, last)
        total_saved += saved

    # Генерируем планы от начала следующего месяца на 35 дней вперёд
    next_month_first = (date(today.year, today.month, 1) + timedelta(days=32)).replace(day=1)
    generated = _generate_plans(db, restaurant_id, date.today(), days_ahead=35)

    return {
        "ok": True,
        "facts_saved": total_saved,
        "plans_generated": generated,
    }


class SetDailyPlanRequest(BaseModel):
    restaurant_id: int
    date: str          # YYYY-MM-DD
    sales_plan: Optional[float] = None
    gc_plan: Optional[int] = None


@router.put("/daily-plan")
def set_daily_plan(
    body: SetDailyPlanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Редактирует план одного дня. Разрешено только для сегодня и будущих дат."""
    _get_restaurant(db, body.restaurant_id, current_user)

    try:
        target_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")

    if target_date < date.today():
        raise HTTPException(400, "Нельзя редактировать планы прошедших дат")

    existing = db.query(SalesDailyPlan).filter(
        SalesDailyPlan.restaurant_id == body.restaurant_id,
        SalesDailyPlan.date == target_date,
    ).first()

    av_check = None
    if body.sales_plan and body.gc_plan and body.gc_plan > 0:
        av_check = round(body.sales_plan / body.gc_plan, 2)

    if existing:
        if body.sales_plan is not None:
            existing.sales_plan = body.sales_plan
        if body.gc_plan is not None:
            existing.gc_plan = body.gc_plan
        if av_check is not None:
            existing.av_check_plan = av_check
        existing.is_manual = True
    else:
        db.add(SalesDailyPlan(
            restaurant_id=body.restaurant_id,
            date=target_date,
            sales_plan=body.sales_plan,
            gc_plan=body.gc_plan,
            av_check_plan=av_check,
            is_manual=True,
        ))
    db.commit()
    return {"ok": True}


@router.post("/generate-plans")
def generate_plans(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пересчитывает планы на следующие 35 дней."""
    _get_restaurant(db, restaurant_id, current_user)
    generated = _generate_plans(db, restaurant_id, date.today(), days_ahead=35)
    return {"ok": True, "plans_generated": generated}


@router.get("/export-day")
def export_day_plan(
    restaurant_code: str = Query(..., description="Код ресторана, напр. 02005"),
    day: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Экспорт плана на конкретный день для внешних систем (iiko_sync, checklist).
    Доступен по коду ресторана — не нужно знать internal ID.
    """
    restaurant = db.query(Restaurant).filter(
        Restaurant.code == restaurant_code.strip()
    ).first()
    if not restaurant:
        raise HTTPException(404, f"Ресторан с кодом '{restaurant_code}' не найден")

    try:
        target = date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты, ожидается YYYY-MM-DD")

    plan = db.query(SalesDailyPlan).filter(
        SalesDailyPlan.restaurant_id == restaurant.id,
        SalesDailyPlan.date == target,
    ).first()

    fact = db.query(SalesDailyFact).filter(
        SalesDailyFact.restaurant_id == restaurant.id,
        SalesDailyFact.date == target,
    ).first()

    av_check_plan = None
    if plan and plan.sales_plan and plan.gc_plan and plan.gc_plan > 0:
        av_check_plan = round(float(plan.sales_plan) / plan.gc_plan, 2)

    return {
        "restaurant_code": restaurant.code,
        "restaurant_name": restaurant.name,
        "date": str(target),
        "weekday": WEEKDAYS_RU[target.weekday()],
        "is_holiday": target in KZ_HOLIDAYS,
        "plan": {
            "gc_plan":       plan.gc_plan if plan else None,
            "sales_plan":    float(plan.sales_plan) if plan and plan.sales_plan else None,
            "av_check_plan": av_check_plan,
            "is_manual":     plan.is_manual if plan else False,
        },
        "fact": {
            "gc_fact":       fact.gc_fact if fact else None,
            "sales_fact":    float(fact.sales_fact) if fact and fact.sales_fact else None,
            "av_check_fact": float(fact.av_check_fact) if fact and fact.av_check_fact else None,
        },
    }
