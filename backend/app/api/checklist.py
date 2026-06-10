"""
Checklist API — цифровой чек-лист менеджера смены.

Структура:
- checklist_task_templates — шаблоны задач (засеиваются один раз)
- checklist_submissions    — одна запись на смену (менеджер + дата + тип смены)
- checklist_answers        — ответы по задачам
- checklist_kpi            — KPI смены (план/факт)
"""
from datetime import date, datetime, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.checklist import (
    ChecklistTaskTemplate,
    ChecklistSubmission,
    ChecklistAnswer,
    ChecklistKPI,
)

router = APIRouter(prefix="/api/checklist", tags=["checklist"])


# ── Google Sheets: start-day / status ────────────────────────────────────────

@router.post("/start-day")
def start_day(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Кнопка 'Начать новый день':
    - Запоминает что сегодня день начат (last_checklist_reset_date = today)
    - Запускает утренний сброс + план в Google Sheets (фоновая задача)
    """
    from datetime import date as date_type, datetime, timezone
    from app.tasks.checklist_tasks import start_day_sync_task

    if current_user.role == "store":
        restaurants = current_user.restaurants
    elif current_user.role in ("co", "admin"):
        restaurants = db.query(Restaurant).filter(
            Restaurant.is_active == True,
            Restaurant.google_sheet_url.isnot(None),
        ).all()
    else:
        raise HTTPException(403, "Нет доступа")

    today = date_type.today()
    started = []
    delay = 0
    for restaurant in restaurants:
        if not restaurant.google_sheet_url:
            continue
        restaurant.last_checklist_reset_date = today
        db.commit()
        # Запускаем с задержкой 30 сек между ресторанами — не перегружаем IIKO
        start_day_sync_task.apply_async(args=[restaurant.id], countdown=delay)
        started.append(restaurant.name)
        delay += 30

    return {"ok": True, "started": started, "total_minutes": round(delay / 60, 1)}


@router.post("/start-day/{restaurant_id}")
def start_day_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Начать новый день для конкретного ресторана (только CO/admin).
    Без ограничений — можно запускать несколько раз в день для тестирования.
    """
    from datetime import date as date_type
    from app.tasks.checklist_tasks import start_day_sync_task

    if current_user.role not in ("co", "admin"):
        raise HTTPException(403, "Доступно только для CO/Admin")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    if not restaurant.google_sheet_url:
        raise HTTPException(400, "У ресторана не настроен Google Sheets URL")

    # Обновляем дату (для консистентности)
    restaurant.last_checklist_reset_date = date_type.today()
    db.commit()

    # Запускаем синхронизацию
    start_day_sync_task.delay(restaurant.id)

    return {
        "ok": True,
        "restaurant": restaurant.name,
        "message": "Синхронизация запущена. Проверьте Google Sheets через 10-20 секунд."
    }


@router.post("/clear/{restaurant_id}")
def clear_sheets_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Очищает Google Sheets ресторана (только CO/admin)."""
    from app.tasks.checklist_tasks import clear_sheets_task

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    if current_user.role == "store":
        allowed = [r.id for r in current_user.restaurants]
        if restaurant_id not in allowed:
            raise HTTPException(403, "Нет доступа к этому ресторану")
    elif current_user.role not in ("co", "admin"):
        raise HTTPException(403, "Нет доступа")

    if not restaurant.google_sheet_url:
        raise HTTPException(400, "У ресторана не настроен Google Sheets URL")

    clear_sheets_task.delay(restaurant.id)
    return {"ok": True, "restaurant": restaurant.name,
            "message": "Очистка запущена. Проверьте Google Sheets через 10-20 секунд."}


@router.get("/status")
def checklist_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Статус чек-листа: начат ли сегодня, время последней синхронизации."""
    from datetime import date as date_type

    today = date_type.today()

    if current_user.role == "store":
        restaurants = current_user.restaurants
    else:
        restaurants = db.query(Restaurant).filter(
            Restaurant.is_active == True,
            Restaurant.google_sheet_url.isnot(None),
        ).all()

    result = []
    for r in restaurants:
        if not r.google_sheet_url:
            continue
        result.append({
            "restaurant_id": r.id,
            "restaurant_name": r.name,
            "started_today": r.last_checklist_reset_date == today,
            "last_reset_date": r.last_checklist_reset_date.isoformat() if r.last_checklist_reset_date else None,
            "checklist_start_hour": r.checklist_start_hour,
        })

    return result


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_restaurant(db: Session, restaurant_id: int, user: User) -> Restaurant:
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")
    if user.role not in ("admin", "co"):
        allowed = [r.id for r in user.restaurants]
        if restaurant_id not in allowed:
            raise HTTPException(403, "Нет доступа")
    return restaurant


def _submission_dict(sub: ChecklistSubmission) -> dict:
    return {
        "id": sub.id,
        "restaurant_id": sub.restaurant_id,
        "manager_id": sub.manager_id,
        "manager_name": sub.manager_name,
        "date": sub.date.isoformat(),
        "shift_type": sub.shift_type,
        "status": sub.status,
        "priority_1_text": sub.priority_1_text,
        "priority_2_text": sub.priority_2_text,
        "priority_3_text": sub.priority_3_text,
        "priority_1_done": sub.priority_1_done,
        "priority_1_result": sub.priority_1_result,
        "priority_2_done": sub.priority_2_done,
        "priority_2_result": sub.priority_2_result,
        "priority_3_done": sub.priority_3_done,
        "priority_3_result": sub.priority_3_result,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
    }


# ── Seed templates ────────────────────────────────────────────────────────────

SEED_TEMPLATES = [
    # before_shift
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 1,
     "task_text": "Провести 15-минутку со сменой до приёма/сдачи смены. Убедиться в наличии всех сотрудников", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 2,
     "task_text": "Ознакомиться с кассовым планом на смену", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 3,
     "task_text": "Определить позиции сверхнормативного сброса (по данным IIKO)", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 4,
     "task_text": "Оценить укомплектованность смены, проверить явку сотрудников и их благополучие", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 5,
     "task_text": "Проверить работоспособность оборудования, систем охлаждения, воды", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 6,
     "task_text": "Проверить укомплектованность позиций 'ГМ-ами', расходные материалы", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 7,
     "task_text": "Проверить/проверить нормальность стоков, убедиться в наличии разменной монеты. Записать замечания", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 8,
     "task_text": "Проверить чистоту и готовность зала, туалетов, кухни к открытию", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 9,
     "task_text": "Убедиться в наличии всех ингредиентов, провести визуальный осмотр витрин", "deadline_time": None},
    {"section": "before_shift", "shift_applicability": "all", "sort_order": 10,
     "task_text": "Проверить уровень запасов упаковки, стаканов, трубочек, салфеток", "deadline_time": None},

    # during_people
    {"section": "during_people", "shift_applicability": "all", "sort_order": 1,
     "task_text": "Обеспечить высокий уровень обслуживания гостей в соответствии с требованиями ГМ и Стандартами", "deadline_time": None},
    {"section": "during_people", "shift_applicability": "all", "sort_order": 2,
     "task_text": "Контролировать соблюдение дисциплины и корпоративных стандартов", "deadline_time": None},
    {"section": "during_people", "shift_applicability": "all", "sort_order": 3,
     "task_text": "Контролировать исполнение требований гостей (KPY), принимать жалобы и благодарности", "deadline_time": None},
    {"section": "during_people", "shift_applicability": "all", "sort_order": 4,
     "task_text": "Контролировать укомплектованность смены и наличие необходимых позиций", "deadline_time": None},

    # during_obs
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 1,
     "task_text": "3 боле заказов на мониторе KYS — немедленно реагировать", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 2,
     "task_text": "3 боле пустых стола ЛИС на FC-admin — позвать помощь", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 3,
     "task_text": "3 боле заказов на мониторе BD/Call — ускорить обработку", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 4,
     "task_text": "Запрет информационных систем айкогу нижнего уровня в Production", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 5,
     "task_text": "3 боле заказов в зоне ОАТ/ОКВ — ускорить выдачу", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 6,
     "task_text": "3 боле готовых заказов в зоне выдачи — немедленно вызвать гостей", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 7,
     "task_text": "3 боле заказов в очереди Drive через каналы(кассы) — проверять каждые 30 мин!", "deadline_time": None},
    {"section": "during_obs", "shift_applicability": "all", "sort_order": 8,
     "task_text": "Отследить наличие «типичного» сброса продуктов в категориях «особого внимания»", "deadline_time": None},

    # during_equip
    {"section": "during_equip", "shift_applicability": "all", "sort_order": 1,
     "task_text": "Проверить выполнение процедуры ТТО (техническое текущее обслуживание)", "deadline_time": None},
    {"section": "during_equip", "shift_applicability": "all", "sort_order": 2,
     "task_text": "Обеспечить правильную работу гриля, фритюра, тостера — тест температуры", "deadline_time": None},
    {"section": "during_equip", "shift_applicability": "all", "sort_order": 3,
     "task_text": "Убедиться в работоспособности кассовых аппаратов и киосков самообслуживания", "deadline_time": None},
    {"section": "during_equip", "shift_applicability": "all", "sort_order": 4,
     "task_text": "Проверить уровень масла во фритюрах, зафиксировать показания", "deadline_time": None},

    # evening_proc
    {"section": "evening_proc", "shift_applicability": "all", "sort_order": 1,
     "task_text": "Составить прогноз продаж, предупредить о необходимости дополнительных сотрудников", "deadline_time": None},
    {"section": "evening_proc", "shift_applicability": "all", "sort_order": 2,
     "task_text": "Проверить выполнение вечерних процедур уборки зала и туалетов", "deadline_time": None},
    {"section": "evening_proc", "shift_applicability": "all", "sort_order": 3,
     "task_text": "Провести инвентаризацию критичных продуктов и заказать при необходимости", "deadline_time": None},

    # after_shift
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 1,
     "task_text": "Обсудить выполнение целей и приоритетов с менеджером/ДУ/ресторана", "deadline_time": None},
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 2,
     "task_text": "Передать дела следующему менеджеру смены (устно + в чек-листе)", "deadline_time": None},
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 3,
     "task_text": "Проверить закрытие всех касс, сейфа, сигнализации", "deadline_time": None},
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 4,
     "task_text": "Убедиться, что весь мусор вынесен", "deadline_time": "до 19:00"},
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 5,
     "task_text": "Получить машину (инкассация): сегодня в 19:00", "deadline_time": "19:00"},
    {"section": "after_shift", "shift_applicability": "all", "sort_order": 6,
     "task_text": "Проверить систему видеонаблюдения, обеспечить безопасность закрытия", "deadline_time": None},
]


@router.post("/seed-templates")
def seed_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Засеивает шаблоны задач (только admin). Идемпотентна."""
    if current_user.role != "admin":
        raise HTTPException(403, "Только для admin")

    existing = db.query(ChecklistTaskTemplate).count()
    if existing > 0:
        return {"ok": True, "skipped": True, "existing": existing}

    for t in SEED_TEMPLATES:
        db.add(ChecklistTaskTemplate(**t, is_active=True))
    db.commit()
    return {"ok": True, "seeded": len(SEED_TEMPLATES)}


# ── Task templates ────────────────────────────────────────────────────────────

@router.get("/templates")
def get_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    templates = (
        db.query(ChecklistTaskTemplate)
        .filter(ChecklistTaskTemplate.is_active == True)
        .order_by(ChecklistTaskTemplate.section, ChecklistTaskTemplate.sort_order)
        .all()
    )
    return [
        {
            "id": t.id,
            "section": t.section,
            "shift_applicability": t.shift_applicability,
            "sort_order": t.sort_order,
            "task_text": t.task_text,
            "deadline_time": t.deadline_time,
        }
        for t in templates
    ]


# ── Submissions ───────────────────────────────────────────────────────────────

class CreateSubmissionRequest(BaseModel):
    restaurant_id: int
    date: str               # YYYY-MM-DD
    shift_type: str         # morning / evening / night
    manager_name: Optional[str] = None


@router.post("/submissions")
def create_submission(
    body: CreateSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_restaurant(db, body.restaurant_id, current_user)

    try:
        sub_date = date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, "Неверный формат даты")

    # Проверяем, нет ли уже чек-листа за эту смену
    existing = db.query(ChecklistSubmission).filter(
        ChecklistSubmission.restaurant_id == body.restaurant_id,
        ChecklistSubmission.date == sub_date,
        ChecklistSubmission.shift_type == body.shift_type,
    ).first()
    if existing:
        return _submission_dict(existing)

    sub = ChecklistSubmission(
        restaurant_id=body.restaurant_id,
        manager_id=current_user.id,
        manager_name=body.manager_name or current_user.username,
        date=sub_date,
        shift_type=body.shift_type,
        status="draft",
    )
    db.add(sub)
    db.flush()

    # Создаём заготовки ответов для всех активных шаблонов
    templates = db.query(ChecklistTaskTemplate).filter(
        ChecklistTaskTemplate.is_active == True
    ).all()
    for t in templates:
        db.add(ChecklistAnswer(
            submission_id=sub.id,
            template_id=t.id,
            is_done=None,
        ))

    # KPI запись (пустая)
    db.add(ChecklistKPI(submission_id=sub.id))

    db.commit()
    db.refresh(sub)
    return _submission_dict(sub)


@router.get("/submissions")
def list_submissions(
    restaurant_id: int,
    month: str = Query(None, description="YYYY-MM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_restaurant(db, restaurant_id, current_user)

    q = db.query(ChecklistSubmission).filter(
        ChecklistSubmission.restaurant_id == restaurant_id
    )
    if month:
        import calendar as _cal
        year_m, mon_m = int(month[:4]), int(month[5:7])
        last_day = _cal.monthrange(year_m, mon_m)[1]
        q = q.filter(
            ChecklistSubmission.date >= date.fromisoformat(f"{month}-01"),
            ChecklistSubmission.date <= date.fromisoformat(f"{month}-{last_day:02d}"),
        )
    subs = q.order_by(ChecklistSubmission.date.desc()).limit(60).all()
    return [_submission_dict(s) for s in subs]


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(ChecklistSubmission).filter(ChecklistSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Не найден")
    _get_restaurant(db, sub.restaurant_id, current_user)

    # Answers
    answers = db.query(ChecklistAnswer).filter(
        ChecklistAnswer.submission_id == submission_id
    ).all()
    answers_list = [
        {
            "id": a.id,
            "template_id": a.template_id,
            "is_done": a.is_done,
            "note": a.note,
            "filled_at": a.filled_at.isoformat() if a.filled_at else None,
        }
        for a in answers
    ]

    # KPI
    kpi = db.query(ChecklistKPI).filter(ChecklistKPI.submission_id == submission_id).first()
    kpi_dict = _kpi_to_dict(kpi) if kpi else {}

    return {
        **_submission_dict(sub),
        "answers": answers_list,
        "kpi": kpi_dict,
    }


class UpdateSubmissionRequest(BaseModel):
    manager_name: Optional[str] = None
    priority_1_text: Optional[str] = None
    priority_2_text: Optional[str] = None
    priority_3_text: Optional[str] = None
    priority_1_done: Optional[bool] = None
    priority_1_result: Optional[str] = None
    priority_2_done: Optional[bool] = None
    priority_2_result: Optional[str] = None
    priority_3_done: Optional[bool] = None
    priority_3_result: Optional[str] = None
    status: Optional[str] = None  # draft / submitted


@router.patch("/submissions/{submission_id}")
def update_submission(
    submission_id: int,
    body: UpdateSubmissionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(ChecklistSubmission).filter(ChecklistSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Не найден")
    _get_restaurant(db, sub.restaurant_id, current_user)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(sub, field, value)

    if body.status == "submitted" and not sub.submitted_at:
        sub.submitted_at = datetime.now(timezone.utc)

    db.commit()
    return _submission_dict(sub)


# ── Answers ───────────────────────────────────────────────────────────────────

class UpsertAnswerRequest(BaseModel):
    template_id: int
    is_done: Optional[bool] = None
    note: Optional[str] = None


@router.put("/submissions/{submission_id}/answers")
def upsert_answer(
    submission_id: int,
    body: UpsertAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(ChecklistSubmission).filter(ChecklistSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission не найден")
    _get_restaurant(db, sub.restaurant_id, current_user)

    answer = db.query(ChecklistAnswer).filter(
        ChecklistAnswer.submission_id == submission_id,
        ChecklistAnswer.template_id == body.template_id,
    ).first()

    if answer:
        if body.is_done is not None:
            answer.is_done = body.is_done
        if body.note is not None:
            answer.note = body.note
        answer.filled_at = datetime.now(timezone.utc)
    else:
        answer = ChecklistAnswer(
            submission_id=submission_id,
            template_id=body.template_id,
            is_done=body.is_done,
            note=body.note,
        )
        db.add(answer)

    db.commit()
    return {"ok": True}


# ── KPI ───────────────────────────────────────────────────────────────────────

def _kpi_to_dict(kpi: ChecklistKPI) -> dict:
    fields = [
        "sales_plan", "sales_fact_morning", "sales_fact_evening",
        "gc_plan", "gc_fact_morning", "gc_fact_evening",
        "av_check_plan", "av_check_fact_morning", "av_check_fact_evening",
        "pct_dt_plan", "pct_kiosk_plan", "pct_cafe_plan", "pct_dlv_plan",
        "pct_dt_fact_m", "pct_dt_fact_e",
        "pct_kiosk_fact_m", "pct_kiosk_fact_e",
        "pct_cafe_fact_m", "pct_cafe_fact_e",
        "pct_dlv_fact_m", "pct_dlv_fact_e",
        "rating_gm_voice_plan", "rating_gm_voice_fact_m", "rating_gm_voice_fact_e",
        "rating_1and2_plan", "rating_1and2_fact_m", "rating_1and2_fact_e",
        "oepe_plan", "oepe_fact_morning", "oepe_fact_evening",
        "gcpch_plan", "gcpch_fact_morning", "gcpch_fact_evening",
        "waste_state_plan", "waste_state_fact",
        "dlv_orders_plan", "dlv_orders_fact_m", "dlv_orders_fact_e",
    ]
    return {"id": kpi.id, **{f: (float(getattr(kpi, f)) if getattr(kpi, f) is not None else None) for f in fields}}


class UpdateKPIRequest(BaseModel):
    sales_plan: Optional[float] = None
    sales_fact_morning: Optional[float] = None
    sales_fact_evening: Optional[float] = None
    gc_plan: Optional[int] = None
    gc_fact_morning: Optional[int] = None
    gc_fact_evening: Optional[int] = None
    av_check_plan: Optional[float] = None
    av_check_fact_morning: Optional[float] = None
    av_check_fact_evening: Optional[float] = None
    pct_dt_plan: Optional[float] = None
    pct_kiosk_plan: Optional[float] = None
    pct_cafe_plan: Optional[float] = None
    pct_dlv_plan: Optional[float] = None
    pct_dt_fact_m: Optional[float] = None
    pct_dt_fact_e: Optional[float] = None
    pct_kiosk_fact_m: Optional[float] = None
    pct_kiosk_fact_e: Optional[float] = None
    pct_cafe_fact_m: Optional[float] = None
    pct_cafe_fact_e: Optional[float] = None
    pct_dlv_fact_m: Optional[float] = None
    pct_dlv_fact_e: Optional[float] = None
    rating_gm_voice_plan: Optional[float] = None
    rating_gm_voice_fact_m: Optional[float] = None
    rating_gm_voice_fact_e: Optional[float] = None
    rating_1and2_plan: Optional[float] = None
    rating_1and2_fact_m: Optional[float] = None
    rating_1and2_fact_e: Optional[float] = None
    oepe_plan: Optional[int] = None
    oepe_fact_morning: Optional[int] = None
    oepe_fact_evening: Optional[int] = None
    gcpch_plan: Optional[float] = None
    gcpch_fact_morning: Optional[float] = None
    gcpch_fact_evening: Optional[float] = None
    waste_state_plan: Optional[float] = None
    waste_state_fact: Optional[float] = None
    dlv_orders_plan: Optional[int] = None
    dlv_orders_fact_m: Optional[int] = None
    dlv_orders_fact_e: Optional[int] = None


@router.patch("/submissions/{submission_id}/kpi")
def update_kpi(
    submission_id: int,
    body: UpdateKPIRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sub = db.query(ChecklistSubmission).filter(ChecklistSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission не найден")
    _get_restaurant(db, sub.restaurant_id, current_user)

    kpi = db.query(ChecklistKPI).filter(ChecklistKPI.submission_id == submission_id).first()
    if not kpi:
        kpi = ChecklistKPI(submission_id=submission_id)
        db.add(kpi)

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(kpi, field, value)

    db.commit()
    db.refresh(kpi)
    return _kpi_to_dict(kpi)


# ── PDF export ────────────────────────────────────────────────────────────────

@router.get("/submissions/{submission_id}/pdf")
def download_pdf(
    submission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Генерирует PDF чек-листа для указанной смены."""
    sub = db.query(ChecklistSubmission).filter(ChecklistSubmission.id == submission_id).first()
    if not sub:
        raise HTTPException(404, "Submission не найден")

    restaurant = _get_restaurant(db, sub.restaurant_id, current_user)

    answers = db.query(ChecklistAnswer).filter(ChecklistAnswer.submission_id == submission_id).all()
    kpi     = db.query(ChecklistKPI).filter(ChecklistKPI.submission_id == submission_id).first()
    templates = (
        db.query(ChecklistTaskTemplate)
        .filter(ChecklistTaskTemplate.is_active == True)
        .order_by(ChecklistTaskTemplate.section, ChecklistTaskTemplate.sort_order)
        .all()
    )

    sub_dict = {
        "id":               sub.id,
        "date":             sub.date.isoformat(),
        "shift_type":       sub.shift_type,
        "status":           sub.status,
        "manager_name":     sub.manager_name,
        "submitted_at":     sub.submitted_at.isoformat() if sub.submitted_at else None,
        "priority_1_text":  sub.priority_1_text,
        "priority_2_text":  sub.priority_2_text,
        "priority_3_text":  sub.priority_3_text,
        "priority_1_done":  sub.priority_1_done,
        "priority_1_result":sub.priority_1_result,
        "priority_2_done":  sub.priority_2_done,
        "priority_2_result":sub.priority_2_result,
        "priority_3_done":  sub.priority_3_done,
        "priority_3_result":sub.priority_3_result,
    }
    answers_list = [
        {"template_id": a.template_id, "is_done": a.is_done, "note": a.note}
        for a in answers
    ]
    templates_list = [
        {"id": t.id, "section": t.section, "sort_order": t.sort_order,
         "task_text": t.task_text, "deadline_time": t.deadline_time}
        for t in templates
    ]
    kpi_dict = _kpi_to_dict(kpi) if kpi else {}

    from app.services.checklist_pdf import generate_checklist_pdf
    pdf_bytes = generate_checklist_pdf(
        submission=sub_dict,
        answers=answers_list,
        templates=templates_list,
        kpi=kpi_dict,
        restaurant_name=restaurant.name,
    )

    filename = f"checklist_{sub.date}_{sub.shift_type}_{sub.id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
