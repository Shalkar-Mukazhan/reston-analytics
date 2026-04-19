"""
Celery задачи для генерации отчётов в фоне.
Тяжёлые операции (запросы к IIKO + расчёты) не блокируют браузер пользователя.
Результат сохраняется в таблицу report_items (не в Excel).
Excel генерируется по запросу через /api/reports/{id}/download.
"""
import traceback
import calendar
from datetime import date, timedelta

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal


def get_week_periods(year: int, month: int) -> list:
    """
    Как в оригинальном app.py:
    - Неделя 1 начинается с 1-го числа месяца, заканчивается первым воскресеньем.
    - Каждая следующая неделя — с понедельника по воскресенье.
    - Остаток дней после последней полной недели (без воскресенья) НЕ включается.
    Возвращает список (week_num, date_start, date_end).
    """
    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    weeks = []
    week_num = 1
    current_start = first_day

    while current_start <= last_day:
        days_until_sunday = (6 - current_start.weekday()) % 7
        current_end = current_start + timedelta(days=days_until_sunday)

        if current_end > last_day:
            break  # остаток без воскресенья — не полная неделя

        weeks.append((week_num, current_start, current_end))
        week_num += 1
        current_start = current_end + timedelta(days=1)

    return weeks


def parse_period(period: str) -> tuple[str, str, date, date]:
    """
    Преобразует строку периода в date_from/date_to для IIKO OLAP.
    IIKO OLAP ожидает date_to ИСКЛЮЧИТЕЛЬНУЮ (следующий день T00:00:00).
    Формат: "2026-03" или "2026-03-W2"
    Возвращает: (iiko_date_from, iiko_date_to, date_from, date_to)
    """
    if "W" in period:
        year_str, rest = period.split("-", 1)
        month_str, week_str = rest.split("-W")
        year, month, week_num = int(year_str), int(month_str), int(week_str)

        weeks = get_week_periods(year, month)
        if week_num < 1 or week_num > len(weeks):
            raise ValueError(
                f"Неделя {week_num} не существует для {year}-{month:02d}. "
                f"Доступных недель: {len(weeks)}."
            )
        _, day_start, day_end = weeks[week_num - 1]
        iiko_from = f"{day_start.strftime('%Y-%m-%d')}T00:00:00"
        iiko_to   = f"{(day_end + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00"
        return iiko_from, iiko_to, day_start, day_end
    else:
        year_str, month_str = period.split("-")
        year, month = int(year_str), int(month_str)
        day_start = date(year, month, 1)
        day_end = date(year, month, calendar.monthrange(year, month)[1])
        iiko_from = f"{day_start.strftime('%Y-%m-%d')}T00:00:00"
        iiko_to   = f"{(day_end + timedelta(days=1)).strftime('%Y-%m-%d')}T00:00:00"
        return iiko_from, iiko_to, day_start, day_end


@celery_app.task(bind=True)
def generate_report_task(self, report_id: int):
    db = SessionLocal()
    try:
        import pandas as pd
        from app.models.report import Report, ReportItem
        from app.models.restaurant import Restaurant
        from app.models.catalog import ProductCatalog, ProductGroup, WasteRate
        from app.services.iiko import fetch_olap
        from app.services.waste_calc import build_report_dataframe

        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            return {"error": "Report not found"}

        report.status = "in_progress"
        db.commit()

        restaurant = db.query(Restaurant).filter(Restaurant.id == report.restaurant_id).first()

        # ── 1. Вычисляем даты периода (как в оригинальном app.py) ────────
        date_from, date_to, d_from, d_to = parse_period(report.period)

        report.date_from = d_from
        report.date_to = d_to
        db.commit()

        # ── 2. Получаем данные из IIKO ────────────────────────────────────
        sales_preset = restaurant.get_preset("sales") or ""
        writeoff_preset = restaurant.get_preset("writeoff") or ""
        inventory_preset = restaurant.get_preset("inventory") or ""
        revenue_net_preset = restaurant.get_preset("revenue_net") or ""
        complete_waste_preset = restaurant.get_preset("complete_waste") or ""

        sales_raw = fetch_olap(db, restaurant, sales_preset, date_from, date_to) if sales_preset else []
        writeoffs_raw = fetch_olap(db, restaurant, writeoff_preset, date_from, date_to) if writeoff_preset else []
        inventory_raw = fetch_olap(db, restaurant, inventory_preset, date_from, date_to) if inventory_preset else []

        # revenue_net и complete_waste — вспомогательные, не должны ломать основной task
        try:
            revenue_net_raw = fetch_olap(db, restaurant, revenue_net_preset, date_from, date_to) if revenue_net_preset else []
        except Exception:
            revenue_net_raw = []
        try:
            complete_waste_raw = fetch_olap(db, restaurant, complete_waste_preset, date_from, date_to) if complete_waste_preset else []
        except Exception:
            complete_waste_raw = []

        # Фильтруем по department_name как в оригинальном app.py
        dept = restaurant.department_name or restaurant.name

        def filter_by_dept(rows):
            if not rows:
                return rows
            if rows and "Department" in rows[0]:
                return [r for r in rows if r.get("Department") == dept]
            return rows

        sales = filter_by_dept(sales_raw)
        writeoffs = filter_by_dept(writeoffs_raw)
        inventory = filter_by_dept(inventory_raw)
        revenue_net_rows = filter_by_dept(revenue_net_raw)
        complete_waste_rows = filter_by_dept(complete_waste_raw)

        # ── 3. Строим refs_goods из БД ────────────────────────────────────
        # outerjoin: берём ВСЕ товары из catalog, даже без группы (group_id nullable с 0014)
        products = (
            db.query(ProductCatalog, ProductGroup)
            .outerjoin(ProductGroup, ProductCatalog.group_id == ProductGroup.id)
            .all()
        )
        # Ключ джойна: product_article (IIKO num/артикул, именно это OLAP отдаёт в Product.Num)
        # Fallback на product_num если article не заполнен
        refs_goods = pd.DataFrame([
            {
                "ProductNum": p.product_article or p.product_num,
                "product_catalog_id": p.id,
                "product_name": p.name,
                "Группа": g.name if g else None,
                "Ед. изм.": p.unit_type or "шт",
            }
            for p, g in products
            if (p.product_article or p.product_num)  # пропускаем товары без обоих ключей
        ])

        # ── 4. Строим group_rates из БД ───────────────────────────────────
        rates = (
            db.query(WasteRate, ProductGroup)
            .join(ProductGroup, WasteRate.group_id == ProductGroup.id)
            .filter(WasteRate.restaurant_id == restaurant.id)
            .all()
        )
        group_rates = pd.DataFrame([
            {
                "restaurant_code": restaurant.code,
                "group": r.rate_pct and g.name,  # use group name as key
                "Группа": g.name,
                "rate_pct": r.rate_pct,
            }
            for r, g in rates
        ])
        # waste_calc ожидает столбец "Группа" в rates — передадим уже переименованный
        group_rates_for_calc = group_rates[["Группа", "rate_pct"]].rename(
            columns={"rate_pct": "Норма %"}
        )

        # ── 5. Расчёт ─────────────────────────────────────────────────────
        df = build_report_dataframe(
            sales=sales,
            writeoffs=writeoffs,
            inventory=inventory,
            refs_goods=refs_goods,
            group_rates_by_group=group_rates_for_calc,
        )

        # ── 6. Сохраняем строки в report_items ───────────────────────────
        # Удаляем старые строки если отчёт перегенерируется
        db.query(ReportItem).filter(ReportItem.report_id == report_id).delete()

        product_id_map   = {row["ProductNum"]: row["product_catalog_id"] for _, row in refs_goods.iterrows()}
        product_name_map = {row["ProductNum"]: row["product_name"]       for _, row in refs_goods.iterrows()}

        items = []
        for _, row in df.iterrows():
            sales_qty = float(row.get("Реализация", 0) or 0)
            writeoff_qty = float(row.get("Уже списано", 0) or 0)
            written_off_pct = round(writeoff_qty / sales_qty * 100, 2) if sales_qty > 0 else 0.0
            pnum = str(row.get("ProductNum", "")).strip()

            item = ReportItem(
                report_id=report_id,
                product_id=product_id_map.get(pnum),
                product_num=pnum or None,
                product_name=product_name_map.get(pnum),
                sales_qty=sales_qty,
                sales_sum=float(row.get("Реализация сумма", 0) or 0),
                writeoff_qty=writeoff_qty,
                writeoff_sum=float(row.get("Уже списано сумма", 0) or 0),
                inventory_qty=float(row.get("Инвентаризация", 0) or 0),
                inventory_sum=float(row.get("Инвентаризация сумма", 0) or 0),
                allowed_qty=float(row.get("Допустимо", 0) or 0),
                to_writeoff_qty=float(row.get("К списанию", 0) or 0),
                written_off_pct=written_off_pct,
                is_over_limit=bool(row.get("Сверх нормы", 0)),
                status=str(row.get("status", "ok")),
                comment=str(row.get("comment", "")) or None,
            )
            items.append(item)

        db.bulk_save_objects(items)
        report.status = "ready"
        db.commit()

        # ── 7. Считаем и сохраняем метрики ───────────────────────────────
        from app.models.report import WasteMetric

        # Недостача из инвентаризации (отрицательные суммы)
        shortage_sum = sum(
            abs(float(r.get("Инвентаризация сумма", 0) or 0))
            for _, r in df.iterrows()
            if float(r.get("Инвентаризация сумма", 0) or 0) < 0
        )
        to_writeoff_qty = sum(float(r.get("К списанию", 0) or 0) for _, r in df.iterrows())
        over_limit_count = int(df["Сверх нормы"].sum()) if "Сверх нормы" in df.columns else 0

        # Выручка: используем revenue_net пресет (как в app.py), иначе — sales_sum
        revenue_sum = 0.0
        if revenue_net_rows:
            rev_col = "DishDiscountSumInt.withoutVAT"
            df_rev = pd.DataFrame(revenue_net_rows)
            if rev_col in df_rev.columns:
                revenue_sum = float(df_rev[rev_col].apply(lambda x: float(str(x).replace(",", ".")) if x else 0).sum())
        if revenue_sum == 0.0:
            revenue_sum = sum(float(r.get("Реализация сумма", 0) or 0) for _, r in df.iterrows())

        # Полное списание: используем complete_waste пресет (как в app.py), иначе — writeoff_sum
        writeoff_sum = 0.0
        if complete_waste_rows:
            waste_col = "Sum.ResignedSum"
            df_cw = pd.DataFrame(complete_waste_rows)
            if waste_col in df_cw.columns:
                writeoff_sum = float(df_cw[waste_col].apply(lambda x: abs(float(str(x).replace(",", ".")) if x else 0)).sum())
        if writeoff_sum == 0.0:
            writeoff_sum = sum(float(r.get("Уже списано сумма", 0) or 0) for _, r in df.iterrows())

        shortage_pct    = round(shortage_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
        writeoff_pct    = round(writeoff_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
        waste_pct       = round((shortage_sum + writeoff_sum) / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0

        # Upsert: обновляем если есть, иначе создаём (не удаляем — сохраняем created_at)
        from datetime import timezone as _tz
        existing_metric = db.query(WasteMetric).filter(
            WasteMetric.restaurant_id == restaurant.id,
            WasteMetric.period == report.period,
        ).first()
        now = datetime.now(_tz.utc)
        if existing_metric:
            existing_metric.revenue_sum        = round(revenue_sum, 2)
            existing_metric.shortage_sum       = round(shortage_sum, 2)
            existing_metric.complete_waste_sum = round(writeoff_sum, 2)
            existing_metric.waste_pct          = waste_pct
            existing_metric.shortage_pct       = shortage_pct
            existing_metric.writeoff_pct       = writeoff_pct
            existing_metric.to_writeoff_qty    = to_writeoff_qty
            existing_metric.over_limit_count   = over_limit_count
            existing_metric.report_id          = report_id
            existing_metric.updated_at         = now
        else:
            db.add(WasteMetric(
                restaurant_id=restaurant.id,
                period=report.period,
                revenue_sum=round(revenue_sum, 2),
                shortage_sum=round(shortage_sum, 2),
                complete_waste_sum=round(writeoff_sum, 2),
                waste_pct=waste_pct,
                shortage_pct=shortage_pct,
                writeoff_pct=writeoff_pct,
                to_writeoff_qty=to_writeoff_qty,
                over_limit_count=over_limit_count,
                report_id=report_id,
                updated_at=now,
            ))
        db.commit()

        return {"status": "ready", "items_count": len(items)}

    except Exception as e:
        db.rollback()
        from app.models.report import Report
        report = db.query(Report).filter(Report.id == report_id).first()
        if report:
            report.status = "error"
            report.error_message = str(e)[:1000]
            db.commit()
        return {"status": "error", "error": traceback.format_exc()}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.report_tasks.sync_iiko_analytics_task")
def sync_iiko_analytics_task(self, restaurant_id: int, year: int):
    """
    Синхронизация revenue_net и complete_waste из IIKO по месяцам за год.
    Переносит логику из /api/analytics/sync-iiko в Celery (не блокирует API поток).
    """
    import calendar as _cal
    import pandas as pd
    from datetime import date as _date, datetime as _dt, timezone as _tz

    db = SessionLocal()
    try:
        from app.models.restaurant import Restaurant
        from app.models.report import WasteMetric
        from app.services.iiko import fetch_olap

        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not restaurant:
            return {"error": "Restaurant not found"}

        revenue_preset = restaurant.get_preset("revenue_net")
        waste_preset = restaurant.get_preset("complete_waste")
        dept = restaurant.department_name or restaurant.name

        def filter_by_dept(rows):
            if not rows:
                return rows
            if rows and "Department" in rows[0]:
                return [r for r in rows if r.get("Department") == dept]
            return rows

        now = _dt.now(_tz.utc)
        max_month = now.month if now.year == year else 12
        results = []
        errors = []

        for mn in range(1, max_month + 1):
            period = f"{year}-{mn:02d}"
            day_start = _date(year, mn, 1)
            next_month_start = _date(year, mn + 1, 1) if mn < 12 else _date(year + 1, 1, 1)
            iiko_from = f"{day_start.strftime('%Y-%m-%d')}T00:00:00"
            iiko_to = f"{next_month_start.strftime('%Y-%m-%d')}T00:00:00"

            revenue_sum = 0.0
            complete_waste_sum = 0.0

            try:
                if revenue_preset:
                    raw = fetch_olap(db, restaurant, revenue_preset, iiko_from, iiko_to)
                    rows = filter_by_dept(raw)
                    if rows:
                        df = pd.DataFrame(rows)
                        col = "DishDiscountSumInt.withoutVAT"
                        if col in df.columns:
                            revenue_sum = float(df[col].apply(
                                lambda x: float(str(x).replace(",", ".")) if x else 0
                            ).sum())

                if waste_preset:
                    raw = fetch_olap(db, restaurant, waste_preset, iiko_from, iiko_to)
                    rows = filter_by_dept(raw)
                    if rows:
                        df = pd.DataFrame(rows)
                        col = "Sum.ResignedSum"
                        if col in df.columns:
                            complete_waste_sum = float(df[col].apply(
                                lambda x: abs(float(str(x).replace(",", ".")) if x else 0)
                            ).sum())
            except Exception as e:
                errors.append({"period": period, "error": str(e)})
                continue

            existing_metric = db.query(WasteMetric).filter(
                WasteMetric.restaurant_id == restaurant_id,
                WasteMetric.period == period,
            ).first()

            sho = float(existing_metric.shortage_sum or 0) if existing_metric else 0.0
            wri = complete_waste_sum
            rev = revenue_sum
            waste_pct    = round((sho + wri) / rev * 100, 4) if rev > 0 else 0.0
            shortage_pct = round(sho / rev * 100, 4) if rev > 0 else 0.0
            writeoff_pct = round(wri / rev * 100, 4) if rev > 0 else 0.0

            from datetime import timezone as _tz2
            now2 = _dt.now(_tz2.utc)
            if existing_metric:
                existing_metric.revenue_sum        = round(rev, 2)
                existing_metric.complete_waste_sum = round(wri, 2)
                existing_metric.waste_pct          = waste_pct
                existing_metric.shortage_pct       = shortage_pct
                existing_metric.writeoff_pct       = writeoff_pct
                existing_metric.updated_at         = now2
            else:
                db.add(WasteMetric(
                    restaurant_id=restaurant_id,
                    report_id=None,
                    period=period,
                    revenue_sum=round(rev, 2),
                    shortage_sum=0.0,
                    complete_waste_sum=round(wri, 2),
                    shortage_pct=shortage_pct,
                    writeoff_pct=writeoff_pct,
                    waste_pct=waste_pct,
                    to_writeoff_qty=0.0,
                    over_limit_count=0,
                    updated_at=now2,
                ))

            results.append({"period": period, "revenue_sum": round(rev, 2), "waste_pct": waste_pct})

        db.commit()
        return {"status": "ok", "restaurant_id": restaurant_id, "year": year,
                "synced": len(results), "errors": errors, "months": results}

    except Exception as e:
        db.rollback()
        return {"status": "error", "error": traceback.format_exc()}
    finally:
        db.close()


@celery_app.task(bind=True, name="app.tasks.report_tasks.sync_all_iiko_analytics_task")
def sync_all_iiko_analytics_task(self):
    """
    Ночная задача: запускает синхронизацию из IIKO для всех активных ресторанов
    за текущий месяц. Запускается автоматически через Celery Beat в 03:00 Алматы.
    """
    from datetime import date as _date
    from app.services.telegram import alert_ok, alert_error
    db = SessionLocal()
    try:
        from app.models.restaurant import Restaurant
        restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()
        now = _date.today()
        year = now.year
        started = []
        for r in restaurants:
            task = sync_iiko_analytics_task.delay(r.id, year)
            started.append({"restaurant_id": r.id, "task_id": task.id})
        alert_ok(
            "Ночной синк аналитики запущен",
            f"Ресторанов: {len(started)} | {now.strftime('%d.%m.%Y')} 03:00"
        )
        return {"year": year, "started": len(started), "tasks": started}
    except Exception as e:
        alert_error("Ночной синк аналитики: ошибка", str(e))
        raise
    finally:
        db.close()


@celery_app.task(bind=True)
def refresh_metrics_task(self, restaurant_id: int, period: str):
    """
    Лёгкий пересчёт метрик без генерации полного отчёта.
    Тянет только 3 OLAP пресета: revenue_net, complete_waste, inventory.
    Не трогает report_items, не меняет статус отчётов.
    """
    db = SessionLocal()
    try:
        import pandas as pd
        from app.models.restaurant import Restaurant
        from app.models.report import WasteMetric
        from app.services.iiko import fetch_olap

        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not restaurant:
            return {"error": "Restaurant not found"}

        date_from, date_to, _, _ = parse_period(period)
        dept = restaurant.department_name or restaurant.name

        def _fetch(preset_type: str) -> list:
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

        revenue_rows      = _fetch("revenue_net")
        complete_waste_rows = _fetch("complete_waste")
        inventory_rows    = _fetch("inventory")

        # Revenue
        revenue_sum = 0.0
        if revenue_rows:
            df_rev = pd.DataFrame(revenue_rows)
            col = "DishDiscountSumInt.withoutVAT"
            if col in df_rev.columns:
                revenue_sum = float(df_rev[col].apply(
                    lambda x: float(str(x).replace(",", ".")) if x else 0
                ).sum())

        # Complete waste
        writeoff_sum = 0.0
        if complete_waste_rows:
            df_cw = pd.DataFrame(complete_waste_rows)
            col = "Sum.ResignedSum"
            if col in df_cw.columns:
                writeoff_sum = float(df_cw[col].apply(
                    lambda x: abs(float(str(x).replace(",", ".")) if x else 0)
                ).sum())

        # Shortage из инвентаризации (отрицательные суммы)
        shortage_sum = 0.0
        if inventory_rows:
            df_inv = pd.DataFrame(inventory_rows)
            sum_col = "Sum.ResignedSum"
            if sum_col in df_inv.columns:
                df_inv[sum_col] = df_inv[sum_col].apply(
                    lambda x: float(str(x).replace(",", ".")) if x else 0
                )
                shortage_sum = float(df_inv[df_inv[sum_col] < 0][sum_col].sum())
                shortage_sum = abs(shortage_sum)

        shortage_pct = round(shortage_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
        writeoff_pct = round(writeoff_sum / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0
        waste_pct    = round((shortage_sum + writeoff_sum) / revenue_sum * 100, 4) if revenue_sum > 0 else 0.0

        # Upsert — сохраняем без report_id (независимо от отчётов)
        existing = db.query(WasteMetric).filter(
            WasteMetric.restaurant_id == restaurant_id,
            WasteMetric.period == period,
        ).first()

        from datetime import timezone as _tz3
        now3 = datetime.now(_tz3.utc)
        if existing:
            existing.revenue_sum        = round(revenue_sum, 2)
            existing.shortage_sum       = round(shortage_sum, 2)
            existing.complete_waste_sum = round(writeoff_sum, 2)
            existing.shortage_pct       = shortage_pct
            existing.writeoff_pct       = writeoff_pct
            existing.waste_pct          = waste_pct
            existing.updated_at         = now3
        else:
            db.add(WasteMetric(
                restaurant_id=restaurant_id,
                period=period,
                revenue_sum=round(revenue_sum, 2),
                shortage_sum=round(shortage_sum, 2),
                complete_waste_sum=round(writeoff_sum, 2),
                shortage_pct=shortage_pct,
                writeoff_pct=writeoff_pct,
                waste_pct=waste_pct,
                to_writeoff_qty=0,
                over_limit_count=0,
                updated_at=now3,
            ))
        db.commit()

        return {
            "status": "ok",
            "period": period,
            "revenue_sum": round(revenue_sum, 2),
            "waste_pct": waste_pct,
        }

    except Exception as e:
        db.rollback()
        return {"status": "error", "error": traceback.format_exc()}
    finally:
        db.close()
