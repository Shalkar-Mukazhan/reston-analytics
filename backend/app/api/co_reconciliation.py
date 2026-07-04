"""
CO Акты сверки — сверка присланного поставщиком акта (xls/xlsx/pdf) с
приходными накладными, реально проведёнными в iiko (без OCR/LLM,
детерминированный разбор файла + прямой запрос в iiko по supplierId).

POST /api/co/reconciliation/check — распознать файл и сверить (без сохранения)
POST /api/co/reconciliation/save  — сохранить результат сверки
GET  /api/co/reconciliation/      — список сохранённых актов
GET  /api/co/reconciliation/{id}  — детали сохранённого акта
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant_utils import load_restaurant
from app.api.co_auth import get_current_co_user, CoUser
from app.models.co_models import CoRestaurant, CoSupplier, CoReconciliationAct

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/co/reconciliation", tags=["co-reconciliation"])

_ALLOWED_EXT = (".xls", ".xlsx", ".pdf")
MAX_FILE_SIZE = 10 * 1024 * 1024
_DATE_TOLERANCE_DAYS = 2


def _check_access(user: CoUser, restaurant_id: int, db) -> CoRestaurant:
    restaurant = load_restaurant(db, restaurant_id, user)
    if user.role != "admin" and restaurant_id not in [r.id for r in user.restaurants]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому ресторану",
        )
    return restaurant


def _days_apart(d1: str | None, d2: str | None) -> int | None:
    if not d1 or not d2:
        return None
    try:
        return abs((datetime.strptime(d1, "%Y-%m-%d") - datetime.strptime(d2, "%Y-%m-%d")).days)
    except ValueError:
        return None


def _dates_close(d1: str | None, d2: str | None, tolerance: int = _DATE_TOLERANCE_DAYS) -> bool:
    # ВАЖНО: `_days_apart(...) or big_number` сломан для diff=0 (0 falsy в Python)
    # — точное совпадение дат ошибочно считалось бы "неизвестным". Сравниваем с None явно.
    diff = _days_apart(d1, d2)
    return diff is not None and diff <= tolerance


@router.post("/check")
async def check_reconciliation(
    restaurant_id: int = Form(...),
    supplier_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    restaurant = _check_access(user, restaurant_id, db)

    filename = file.filename or "file"
    if not filename.lower().endswith(_ALLOWED_EXT):
        raise HTTPException(status_code=400, detail="Поддерживаются: .xls, .xlsx, .pdf")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Файл слишком большой (макс. 10 МБ)")

    from app.services.reconciliation_parser import parse_reconciliation_file
    try:
        parsed = parse_reconciliation_file(file_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Ошибка разбора акта сверки")
        raise HTTPException(status_code=422, detail=f"Не удалось разобрать файл: {e}")

    # ── Поставщик: явно выбран → по БИН из файла → предложить выбрать ──
    supplier: CoSupplier | None = None
    if supplier_id:
        supplier = db.query(CoSupplier).filter(
            CoSupplier.id == supplier_id, CoSupplier.tenant_id == user.tenant_id,
        ).first()

    # Ищем СНАЧАЛА по БИН левой колонки (её всегда занимает поставщик, выставивший
    # акт — так во всех виденных образцах), и только потом — по правой (наш
    # ресторан). Если искать по обоим сразу через IN(...), из-за "мусорных"
    # записей поставщиков с БИН самого ресторана (внутренние поставщики/склады,
    # затесавшиеся в справочник при синхронизации с iiko) можно случайно
    # получить не того поставщика — порядок в IN(...) непредсказуем.
    if not supplier and parsed["left_org"]["bin"]:
        supplier = db.query(CoSupplier).filter(
            CoSupplier.bin == parsed["left_org"]["bin"], CoSupplier.tenant_id == user.tenant_id,
        ).first()
    if not supplier and parsed["right_org"]["bin"]:
        supplier = db.query(CoSupplier).filter(
            CoSupplier.bin == parsed["right_org"]["bin"], CoSupplier.tenant_id == user.tenant_id,
        ).first()

    if not supplier:
        suppliers = db.query(CoSupplier).filter(
            CoSupplier.tenant_id == user.tenant_id, CoSupplier.is_active == True,
        ).order_by(CoSupplier.name).all()
        return {
            "supplier_found": False,
            "candidates": [{"id": s.id, "name": s.name, "bin": s.bin} for s in suppliers],
            "left_org": parsed["left_org"],
            "right_org": parsed["right_org"],
            "period": parsed["period"],
        }

    # Какой блок в файле — "наш" (тот, чей БИН НЕ совпал с поставщиком)
    our_side = "right"
    if parsed["left_org"]["bin"] and parsed["left_org"]["bin"] == supplier.bin:
        our_side = "right"
    elif parsed["right_org"]["bin"] and parsed["right_org"]["bin"] == supplier.bin:
        our_side = "left"

    if not supplier.iiko_id:
        raise HTTPException(
            status_code=422,
            detail=f"У поставщика «{supplier.name}» не задан iiko_id — "
                    "сверка с iiko невозможна, привяжите поставщика на вкладке «Поставщики»",
        )

    # Запрашиваем в iiko узкое окно по фактическим датам строк акта (± допуск
    # на сдвиг даты), а НЕ заявленный в шапке период целиком: строки обычно
    # начинаются позже начала периода (то, что раньше — уже учтено в сальдо
    # на начало и не должно попадать в "лишние" накладные).
    row_dates = sorted(r["date"] for r in parsed["rows"] if r["date"])
    if row_dates:
        query_from = (datetime.strptime(row_dates[0], "%Y-%m-%d") - timedelta(days=_DATE_TOLERANCE_DAYS)).strftime("%Y-%m-%d")
        query_to = (datetime.strptime(row_dates[-1], "%Y-%m-%d") + timedelta(days=_DATE_TOLERANCE_DAYS)).strftime("%Y-%m-%d")
    else:
        query_from = parsed["period"].get("from")
        query_to = parsed["period"].get("to")
    if not query_from or not query_to:
        raise HTTPException(status_code=422, detail="Не удалось определить период акта сверки из файла")

    from app.services.co_iiko import fetch_incoming_invoices
    try:
        iiko_invoices = fetch_incoming_invoices(restaurant, supplier.iiko_id, query_from, query_to)
    except Exception as e:
        logger.exception("Ошибка запроса накладных из iiko")
        raise HTTPException(status_code=502, detail=f"Не удалось получить данные из iiko: {e}")

    matched_ids: set[str] = set()
    annotated_rows = []
    for row in parsed["rows"]:
        our_debit = row[f"{our_side}_debit"]
        our_credit = row[f"{our_side}_credit"]
        row_status = "info"
        matched_invoice = None

        if our_credit:
            # Совпадение по сумме (±1 тенге) и дате (±2 дня — дата акта
            # реализации у поставщика может отличаться от даты оприходования
            # в iiko). Предпочитаем точное совпадение даты.
            candidates = [
                inv for inv in iiko_invoices
                if inv["iiko_id"] not in matched_ids
                and abs(inv["total"] - our_credit) < 1.0
                and _dates_close(inv["date"], row["date"])
            ]
            if candidates:
                candidates.sort(key=lambda inv: _days_apart(inv["date"], row["date"]))
                inv = candidates[0]
                matched_ids.add(inv["iiko_id"])
                row_status = "matched" if inv["date"] == row["date"] else "matched_date_shift"
                matched_invoice = {
                    "iiko_document_number": inv["document_number"],
                    "incoming_document_number": inv["incoming_document_number"],
                    "date": inv["date"],
                    "total": inv["total"],
                }
            else:
                same_date = [
                    inv for inv in iiko_invoices
                    if inv["iiko_id"] not in matched_ids
                    and _dates_close(inv["date"], row["date"])
                ]
                if same_date:
                    same_date.sort(key=lambda inv: _days_apart(inv["date"], row["date"]))
                    row_status = "amount_mismatch"
                    matched_invoice = {"total": same_date[0]["total"], "date": same_date[0]["date"]}
                else:
                    row_status = "missing_in_iiko"
        elif our_debit:
            row_status = "payment"

        annotated_rows.append({
            "date": row["date"],
            "description": row["description"],
            "document_number": row["document_number"],
            "debit": our_debit,
            "credit": our_credit,
            "status": row_status,
            "matched_invoice": matched_invoice,
        })

    extra_invoices = [
        {
            "iiko_id": inv["iiko_id"],
            "document_number": inv["document_number"],
            "incoming_document_number": inv["incoming_document_number"],
            "date": inv["date"],
            "total": inv["total"],
        }
        for inv in iiko_invoices if inv["iiko_id"] not in matched_ids
    ]

    credit_total = round(sum(r["credit"] or 0 for r in annotated_rows), 2)
    debit_total = round(sum(r["debit"] or 0 for r in annotated_rows), 2)
    iiko_invoices_total = round(sum(inv["total"] for inv in iiko_invoices), 2)
    delta = round(iiko_invoices_total - credit_total, 2)

    has_discrepancy = (
        extra_invoices
        or abs(delta) >= 1.0
        or any(r["status"] in ("missing_in_iiko", "amount_mismatch") for r in annotated_rows)
    )

    def _balance(b: dict | None) -> dict | None:
        if not b:
            return None
        debit, credit = b[f"{our_side}_debit"], b[f"{our_side}_credit"]
        if debit is None and credit is None:
            # Наша колонка пустая (обычное дело — акт присылает поставщик,
            # заполняя только свою сторону) → берём цифру с их стороны,
            # переворачивая Дебет/Кредит под нашу перспективу.
            other = "left" if our_side == "right" else "right"
            credit, debit = b[f"{other}_debit"], b[f"{other}_credit"]
        return {"debit": debit, "credit": credit}

    # Фактический период (по датам строк), а не заявленный в шапке акта —
    # именно он используется для запроса к iiko и именно его логично сохранять.
    effective_from = row_dates[0] if row_dates else parsed["period"].get("from")
    effective_to = row_dates[-1] if row_dates else parsed["period"].get("to")

    return {
        "supplier_found": True,
        "supplier": {"id": supplier.id, "name": supplier.name, "bin": supplier.bin},
        "period": {"from": effective_from, "to": effective_to},
        "declared_period": parsed["period"],
        "source_filename": filename,
        "rows": annotated_rows,
        "extra_invoices": extra_invoices,
        "opening_balance": _balance(parsed["opening_balance"]),
        "closing_balance": _balance(parsed["closing_balance"]),
        "totals": {
            "credit_total": credit_total,
            "debit_total": debit_total,
            "iiko_invoices_total": iiko_invoices_total,
            "delta": delta,
        },
        "verdict": "discrepancy" if has_discrepancy else "ok",
        "warnings": parsed["warnings"],
    }


# ── Сохранение / список / детали ────────────────────────────────────────────

class SaveReconciliationRequest(BaseModel):
    restaurant_id: int
    supplier_id: int
    period_from: str
    period_to: str
    credit_total: float
    debit_total: float
    iiko_invoices_total: float
    delta: float
    verdict: str
    rows: list[dict]
    extra_invoices: list[dict]
    source_filename: str | None = None


@router.post("/save")
def save_reconciliation(
    body: SaveReconciliationRequest,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    _check_access(user, body.restaurant_id, db)
    supplier = db.query(CoSupplier).filter(
        CoSupplier.id == body.supplier_id, CoSupplier.tenant_id == user.tenant_id,
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Поставщик не найден")

    try:
        period_from = datetime.strptime(body.period_from, "%Y-%m-%d").date()
        period_to = datetime.strptime(body.period_to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=422, detail="Некорректный формат периода")

    act = CoReconciliationAct(
        restaurant_id=body.restaurant_id,
        supplier_id=body.supplier_id,
        period_from=period_from,
        period_to=period_to,
        credit_total=body.credit_total,
        debit_total=body.debit_total,
        iiko_invoices_total=body.iiko_invoices_total,
        delta=body.delta,
        verdict=body.verdict,
        rows_json=body.rows,
        extra_invoices_json=body.extra_invoices,
        source_filename=body.source_filename,
        created_by=user.id,
    )
    db.add(act)
    db.commit()
    return {"id": act.id}


@router.get("/")
def list_reconciliation_acts(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    accessible = [r.id for r in user.restaurants] if user.role != "admin" else None
    q = db.query(CoReconciliationAct).join(
        CoRestaurant, CoReconciliationAct.restaurant_id == CoRestaurant.id
    ).filter(CoRestaurant.tenant_id == user.tenant_id)
    if accessible is not None:
        q = q.filter(CoReconciliationAct.restaurant_id.in_(accessible))
    if restaurant_id:
        q = q.filter(CoReconciliationAct.restaurant_id == restaurant_id)

    acts = q.order_by(CoReconciliationAct.created_at.desc()).limit(200).all()
    restaurants = {r.id: r for r in db.query(CoRestaurant).filter(
        CoRestaurant.id.in_({a.restaurant_id for a in acts}),
    ).all()}
    suppliers = {s.id: s for s in db.query(CoSupplier).filter(
        CoSupplier.id.in_({a.supplier_id for a in acts}),
    ).all()}

    return [
        {
            "id": a.id,
            "restaurant_id": a.restaurant_id,
            "restaurant_name": restaurants[a.restaurant_id].name if a.restaurant_id in restaurants else None,
            "supplier_id": a.supplier_id,
            "supplier_name": suppliers[a.supplier_id].name if a.supplier_id in suppliers else None,
            "period_from": a.period_from.isoformat(),
            "period_to": a.period_to.isoformat(),
            "credit_total": float(a.credit_total),
            "debit_total": float(a.debit_total),
            "delta": float(a.delta),
            "verdict": a.verdict,
            "created_at": a.created_at.isoformat(),
        }
        for a in acts
    ]


@router.get("/{act_id}")
def get_reconciliation_act(
    act_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    act = db.query(CoReconciliationAct).filter(CoReconciliationAct.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Акт сверки не найден")
    _check_access(user, act.restaurant_id, db)

    supplier = db.query(CoSupplier).filter(CoSupplier.id == act.supplier_id).first()
    restaurant = db.query(CoRestaurant).filter(CoRestaurant.id == act.restaurant_id).first()

    return {
        "id": act.id,
        "restaurant_id": act.restaurant_id,
        "restaurant_name": restaurant.name if restaurant else None,
        "supplier": {"id": supplier.id, "name": supplier.name, "bin": supplier.bin} if supplier else None,
        "period": {"from": act.period_from.isoformat(), "to": act.period_to.isoformat()},
        "rows": act.rows_json,
        "extra_invoices": act.extra_invoices_json,
        "totals": {
            "credit_total": float(act.credit_total),
            "debit_total": float(act.debit_total),
            "iiko_invoices_total": float(act.iiko_invoices_total),
            "delta": float(act.delta),
        },
        "verdict": act.verdict,
        "source_filename": act.source_filename,
        "created_at": act.created_at.isoformat(),
    }


@router.delete("/{act_id}")
def delete_reconciliation_act(
    act_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    act = db.query(CoReconciliationAct).filter(CoReconciliationAct.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Акт сверки не найден")
    _check_access(user, act.restaurant_id, db)
    db.delete(act)
    db.commit()
    return {"ok": True}
