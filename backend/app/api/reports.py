import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.report import Report, ReportItem
from app.models.catalog import ProductCatalog, ProductGroup
from app.models.restaurant import Restaurant
from app.models.audit import AuditLog
from app.tasks.report_tasks import generate_report_task

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/weeks")
def get_weeks(year: int, month: int):
    """Возвращает список доступных недель для месяца (пн–вс, как в app.py)."""
    from app.tasks.report_tasks import get_week_periods
    weeks = get_week_periods(year, month)
    return [
        {
            "week": w,
            "label": f"Неделя {w} ({start.strftime('%d.%m')}–{end.strftime('%d.%m')})",
            "date_from": start.isoformat(),
            "date_to": end.isoformat(),
        }
        for w, start, end in weeks
    ]


class GenerateReportRequest(BaseModel):
    restaurant_id: int
    period: str        # "2024-03" или "2024-03-W1"
    period_type: str = "month"


@router.post("/generate")
def generate_report(
    body: GenerateReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем доступ к ресторану
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if current_user.role != "co":
        allowed_ids = [r.id for r in current_user.restaurants]
        if restaurant.id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")

    # Upsert: если отчёт за этот период уже есть — перезаписываем его
    report = db.query(Report).filter(
        Report.restaurant_id == restaurant.id,
        Report.period == body.period,
    ).first()
    if report:
        report.status = "pending"
        report.user_id = current_user.id
        report.period_type = body.period_type
    else:
        report = Report(
            restaurant_id=restaurant.id,
            user_id=current_user.id,
            period=body.period,
            period_type=body.period_type,
            status="pending",
        )
        db.add(report)
    db.commit()
    db.refresh(report)

    # Запускаем фоновую задачу Celery
    generate_report_task.delay(report.id)

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="generate_report",
        details=f"period={body.period}",
    ))
    db.commit()

    return {"report_id": report.id, "status": "pending"}


@router.get("/{report_id}/status")
def report_status(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return {
        "report_id": report.id,
        "status": report.status,
        "error": report.error_message,
        "created_at": report.created_at,
    }


@router.get("/{report_id}/items")
def report_items(
    report_id: int,
    status: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Строки отчёта для отображения в браузере."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Отчёт не найден")

    query = db.query(ReportItem, ProductCatalog, ProductGroup).outerjoin(
        ProductCatalog, ReportItem.product_id == ProductCatalog.id
    ).outerjoin(
        ProductGroup, ProductCatalog.group_id == ProductGroup.id
    ).filter(ReportItem.report_id == report_id)

    if status:
        query = query.filter(ReportItem.status == status)

    from app.models.catalog import WasteRate
    rates_map = {
        wr.group_id: wr.rate_pct
        for wr in db.query(WasteRate).filter(WasteRate.restaurant_id == report.restaurant_id).all()
    }

    rows = query.all()
    return [
        {
            "id": item.id,
            "product_num": prod.product_num if prod else item.product_num,
            "product_name": prod.name if prod else item.product_name,
            "group": grp.name if grp else None,
            "unit_type": prod.unit_type if prod else None,
            "rate_pct": rates_map.get(grp.id if grp else None, 0.0),
            "sales_qty": item.sales_qty,
            "sales_sum": item.sales_sum or 0,
            "writeoff_qty": item.writeoff_qty,
            "writeoff_sum": item.writeoff_sum or 0,
            "inventory_qty": item.inventory_qty,
            "inventory_sum": item.inventory_sum or 0,
            "allowed_qty": item.allowed_qty,
            "to_writeoff_qty": item.to_writeoff_qty,
            "written_off_pct": item.written_off_pct,
            "is_over_limit": item.is_over_limit,
            "status": item.status,
            "comment": item.comment,
        }
        for item, prod, grp in rows
    ]


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Генерирует Excel из report_items и отдаёт файл."""
    import pandas as pd

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or report.status != "ready":
        raise HTTPException(status_code=404, detail="Отчёт не готов")

    restaurant = db.query(Restaurant).filter(Restaurant.id == report.restaurant_id).first()

    from app.models.catalog import WasteRate

    rows = db.query(ReportItem, ProductCatalog, ProductGroup).outerjoin(
        ProductCatalog, ReportItem.product_id == ProductCatalog.id
    ).outerjoin(
        ProductGroup, ProductCatalog.group_id == ProductGroup.id
    ).filter(ReportItem.report_id == report_id).all()

    # Загружаем нормы для ресторана: group_id → rate_pct
    rates_map = {
        wr.group_id: wr.rate_pct
        for wr in db.query(WasteRate).filter(WasteRate.restaurant_id == report.restaurant_id).all()
    }

    data = []
    for item, prod, grp in rows:
        rate_pct = rates_map.get(grp.id if grp else None, 0.0) or 0.0
        data.append({
            "Ресторан": restaurant.name,
            "Код товара": prod.product_num if prod else (item.product_num or ""),
            "Наименование": prod.name if prod else (item.product_name or ""),
            "Группа": grp.name if grp else "",
            "Ед. изм.": prod.unit_type if prod else "",
            "Реализация": item.sales_qty,
            "Реализация сумма": item.sales_sum or 0,
            "Норма %": rate_pct,
            "Допустимо": item.allowed_qty,
            "Уже списано": item.writeoff_qty,
            "Уже списано сумма": item.writeoff_sum or 0,
            "Списано % от реализации": item.written_off_pct,
            "Инвентаризация": item.inventory_qty,
            "Инвентаризация сумма": item.inventory_sum or 0,
            "К списанию": item.to_writeoff_qty,
            "Комментарий": item.comment or "",
        })

    df = pd.DataFrame(data)
    # Сортировка как в app.py: Инвентаризация desc, К списанию desc
    df["_inv_abs"] = df["Инвентаризация"].abs()
    df = df.sort_values(by=["_inv_abs", "К списанию"], ascending=[False, False]).drop(columns=["_inv_abs"])

    # К_СПИСАНИЮ: Норма % == 1 (100%) и К списанию > 0
    df_writeoff = df[(df["К списанию"] > 0) & (df["Норма %"] == 1)].copy()

    # СВЕРХ_НОРМЫ: частичная ставка, уже списано > допустимо
    df_over = df[(df["Норма %"] < 1) & (df["Норма %"] > 0) & (df["Уже списано"] > df["Допустимо"])].copy()
    if not df_over.empty:
        df_over["Превышение кол-во"] = (df_over["Уже списано"] - df_over["Допустимо"]).clip(lower=0)
        df_over["Превышение %"] = (df_over["Списано % от реализации"] - df_over["Норма %"]).round(2)

    # ПРОБЛЕМНЫЕ: нет нормы или нет категории
    df_problems = df[df["Норма %"] == 0].copy()

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ОТЧЕТ", index=False)
        if not df_writeoff.empty:
            df_writeoff.to_excel(writer, sheet_name="К_СПИСАНИЮ", index=False)
        if not df_over.empty:
            df_over.to_excel(writer, sheet_name="СВЕРХ_НОРМЫ", index=False)
        if not df_problems.empty:
            df_problems.to_excel(writer, sheet_name="ПРОБЛЕМНЫЕ", index=False)
    buf.seek(0)

    filename = f"report_{restaurant.code}_{report.period}.xlsx"

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=report.restaurant_id,
        action="download_report",
        details=f"report_id={report_id}",
    ))
    db.commit()

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{report_id}/post-writeoff")
def post_writeoff_from_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправляет акт списания в IIKO — только строки с rate_pct == 100% и to_writeoff_qty > 0."""
    from app.models.catalog import Account, WasteRate
    from app.services.iiko import post_writeoff

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report or report.status != "ready":
        raise HTTPException(status_code=404, detail="Отчёт не готов")

    restaurant = db.query(Restaurant).filter(Restaurant.id == report.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if not restaurant.store_id:
        raise HTTPException(status_code=400, detail="У ресторана не задан storeId. Выполните синхронизацию складов в Admin.")

    # Нормы ресторана: group_id → rate_pct
    rates_map = {
        wr.group_id: wr.rate_pct
        for wr in db.query(WasteRate).filter(WasteRate.restaurant_id == report.restaurant_id).all()
    }

    # Получаем строки с ненулевым к списанию
    rows = (
        db.query(ReportItem, ProductCatalog, ProductGroup)
        .outerjoin(ProductCatalog, ReportItem.product_id == ProductCatalog.id)
        .outerjoin(ProductGroup, ProductCatalog.group_id == ProductGroup.id)
        .filter(ReportItem.report_id == report_id, ReportItem.to_writeoff_qty > 0)
        .all()
    )

    if not rows:
        raise HTTPException(status_code=400, detail="Нет строк для списания (to_writeoff_qty = 0)")

    # Загружаем аккаунты: account_id → account_iiko_id
    accounts_map = {a.id: a.account_iiko_id for a in db.query(Account).all()}

    # Дата документа = последний день периода 22:00
    # Месяц: 31.03.2026T22:00:00 / Неделя: воскресенье T22:00:00
    date_incoming = report.date_to.strftime("%Y-%m-%dT22:00:00") if report.date_to else \
        report.period.split("-W")[0].replace("-", "-") + "-01T22:00:00"

    # Группируем по accountId — только items с rate_pct == 100%
    from collections import defaultdict
    by_account: dict = defaultdict(list)

    skipped_no_product = []
    skipped_no_account = []
    skipped_not_100pct = []

    for item, prod, grp in rows:
        if not prod or not prod.product_iiko_id:
            skipped_no_product.append(item.id)
            continue
        # Только 100% нормы
        rate_pct = rates_map.get(grp.id if grp else None, 0.0)
        if rate_pct != 100.0:
            skipped_not_100pct.append(prod.product_num if prod else str(item.id))
            continue
        account_iiko_id = accounts_map.get(grp.account_id) if grp else None
        if not account_iiko_id:
            skipped_no_account.append(prod.product_num if prod else str(item.id))
            continue
        by_account[account_iiko_id].append({
            "productId": prod.product_iiko_id,
            "amount": item.to_writeoff_qty,
        })

    if not by_account:
        detail = "Нет товаров для отправки (только rate_pct=100% включается в списание)."
        if skipped_not_100pct:
            detail += f" Пропущено (не 100%): {len(skipped_not_100pct)} шт."
        if skipped_no_product:
            detail += f" Без product_iiko_id: {len(skipped_no_product)} шт."
        if skipped_no_account:
            detail += f" Без accountId: {', '.join(skipped_no_account[:5])}"
        raise HTTPException(status_code=400, detail=detail)

    results = []
    errors = []

    for account_iiko_id, items_list in by_account.items():
        payload = {
            "dateIncoming": date_incoming[:16],
            "status": "NEW",
            "comment": f"Waste Control {restaurant.code} {report.period}",
            "storeId": restaurant.store_id,
            "accountId": account_iiko_id,
            "items": items_list,
        }
        try:
            result = post_writeoff(db, restaurant, payload)
            results.append({"account": account_iiko_id, "items": len(items_list), "response": result})
        except Exception as e:
            err_str = str(e)
            if "is not in current period" in err_str:
                errors.append({
                    "account": account_iiko_id,
                    "error": err_str,
                    "period_closed": True,
                })
            else:
                errors.append({"account": account_iiko_id, "error": err_str})

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="post_writeoff",
        details=f"report_id={report_id}, docs={len(results)}, errors={len(errors)}",
    ))
    db.commit()

    return {
        "docs_sent": len(results),
        "errors": errors,
        "skipped_not_100pct": len(skipped_not_100pct),
        "skipped_no_product": len(skipped_no_product),
        "skipped_no_account": skipped_no_account[:10],
        "results": results,
    }


@router.post("/{report_id}/recalc-metrics")
def recalc_metrics(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Пересчитывает WasteMetric для отчёта:
    - revenue: из revenue_net OLAP (DishDiscountSumInt.withoutVAT)
    - complete_waste: из complete_waste OLAP (Sum.ResignedSum)
    - shortage: из report_items (отрицательная инвентаризация)
    """
    from sqlalchemy import func as sqlfunc
    from app.models.report import WasteMetric
    from app.services.iiko import fetch_olap
    from app.tasks.report_tasks import parse_period
    import pandas as pd

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Отчёт не найден")

    restaurant = db.query(Restaurant).filter(Restaurant.id == report.restaurant_id).first()
    date_from, date_to, _, _ = parse_period(report.period)
    dept = restaurant.department_name or restaurant.name

    def _fetch_safe(preset_type: str) -> list:
        uuid = restaurant.get_preset(preset_type) or ""
        if not uuid:
            return []
        try:
            rows = fetch_olap(db, restaurant, uuid, date_from, date_to)
            if rows and "Department" in rows[0]:
                rows = [r for r in rows if r.get("Department") == dept]
            return rows
        except Exception:
            return []

    # Revenue net
    revenue_rows = _fetch_safe("revenue_net")
    revenue_sum = 0.0
    if revenue_rows:
        df_rev = pd.DataFrame(revenue_rows)
        col = "DishDiscountSumInt.withoutVAT"
        if col in df_rev.columns:
            revenue_sum = float(df_rev[col].apply(lambda x: float(str(x).replace(",", ".")) if x else 0).sum())

    # Complete waste
    cw_rows = _fetch_safe("complete_waste")
    writeoff_sum = 0.0
    if cw_rows:
        df_cw = pd.DataFrame(cw_rows)
        col = "Sum.ResignedSum"
        if col in df_cw.columns:
            writeoff_sum = float(df_cw[col].apply(lambda x: abs(float(str(x).replace(",", ".")) if x else 0)).sum())

    # Shortage из report_items
    shortage_sum = abs(float(
        db.query(sqlfunc.sum(ReportItem.inventory_sum))
        .filter(ReportItem.report_id == report_id, ReportItem.inventory_sum < 0)
        .scalar() or 0
    ))
    to_writeoff_qty = float(db.query(sqlfunc.sum(ReportItem.to_writeoff_qty)).filter(ReportItem.report_id == report_id).scalar() or 0)
    over_limit_count = int(db.query(sqlfunc.count(ReportItem.id)).filter(ReportItem.report_id == report_id, ReportItem.is_over_limit == True).scalar() or 0)

    # Fallback если revenue_net не настроен
    if revenue_sum == 0.0:
        revenue_sum = float(db.query(sqlfunc.sum(ReportItem.sales_sum)).filter(ReportItem.report_id == report_id).scalar() or 0)
    if writeoff_sum == 0.0:
        writeoff_sum = float(db.query(sqlfunc.sum(ReportItem.writeoff_sum)).filter(ReportItem.report_id == report_id).scalar() or 0)

    shortage_pct = round(shortage_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
    writeoff_pct = round(writeoff_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
    waste_pct = round((shortage_sum + writeoff_sum) / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0

    from app.models.report import WasteMetric
    db.query(WasteMetric).filter(
        WasteMetric.restaurant_id == restaurant.id,
        WasteMetric.period == report.period,
    ).delete()
    db.add(WasteMetric(
        restaurant_id=restaurant.id,
        report_id=report_id,
        period=report.period,
        revenue_sum=round(revenue_sum, 2),
        shortage_sum=round(shortage_sum, 2),
        complete_waste_sum=round(writeoff_sum, 2),
        shortage_pct=shortage_pct,
        writeoff_pct=writeoff_pct,
        waste_pct=waste_pct,
        to_writeoff_qty=to_writeoff_qty,
        over_limit_count=over_limit_count,
    ))
    db.commit()

    return {
        "period": report.period,
        "revenue_sum": round(revenue_sum, 2),
        "shortage_sum": round(shortage_sum, 2),
        "complete_waste_sum": round(writeoff_sum, 2),
        "shortage_pct": shortage_pct,
        "writeoff_pct": writeoff_pct,
        "waste_pct": waste_pct,
        "revenue_source": "revenue_net_olap" if restaurant.get_preset("revenue_net") else "sales_sum_fallback",
        "waste_source": "complete_waste_olap" if restaurant.get_preset("complete_waste") else "writeoff_sum_fallback",
    }


@router.get("/")
def list_reports(
    restaurant_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Report)
    if current_user.role != "co":
        allowed_ids = [r.id for r in current_user.restaurants]
        query = query.filter(Report.restaurant_id.in_(allowed_ids))
    elif restaurant_id:
        query = query.filter(Report.restaurant_id == restaurant_id)

    reports = query.order_by(Report.created_at.desc()).limit(100).all()
    return [
        {
            "id": r.id,
            "restaurant_id": r.restaurant_id,
            "period": r.period,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in reports
    ]
