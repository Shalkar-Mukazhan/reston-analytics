"""
API для технологических карт (рецептов).
Синхронизация из IIKO, поиск по ингредиенту, массовое редактирование.
"""
import json
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.catalog import ProductCatalog
from app.models.recipe import AssemblyChart, ChartIngredient, Dish, RecipeChangeLog
from app.models.restaurant import Restaurant
from app.services import iiko as iiko_svc

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class SyncRequest(BaseModel):
    date_from: str = "2020-01-01"
    date_to: Optional[str] = None


class BulkRemoveRequest(BaseModel):
    restaurant_id: int
    ingredient_iiko_uuid: str          # UUID ингредиента для удаления
    chart_ids: list[int]               # ID техкарт из нашей БД
    effective_date: Optional[str] = None  # с какой даты (default = сегодня)


class BulkReplaceRequest(BaseModel):
    restaurant_id: int
    old_ingredient_uuid: str           # что заменяем
    new_ingredient_uuid: str           # на что заменяем
    new_ingredient_name: Optional[str] = None  # название нового (для кеша)
    new_amount_in: float               # новое брутто
    new_amount_middle: Optional[float] = None
    new_amount_out: Optional[float] = None
    chart_ids: list[int]
    effective_date: Optional[str] = None


class BulkUpdateAmountRequest(BaseModel):
    restaurant_id: int
    ingredient_iiko_uuid: str
    new_amount_in: float               # новое брутто
    chart_ids: list[int]
    effective_date: Optional[str] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _ingredient_to_iiko_item(ing: ChartIngredient) -> dict:
    """Конвертирует строку ингредиента в формат IIKO items (без id строки — новая карта)."""
    return {
        "sortWeight": ing.sort_weight,
        "productId": ing.ingredient_iiko_uuid,
        "productSizeSpecification": ing.product_size_spec_id,  # сохраняем шкалу размеров
        "storeSpecification": None,         # null = все подразделения
        "amountIn":   ing.amount_in,
        "amountMiddle": ing.amount_middle or ing.amount_in,
        "amountOut":  ing.amount_out or ing.amount_in,
        "amountIn1":  ing.amount_in1 or 0,
        "amountOut1": ing.amount_out1 or 0,
        "amountIn2":  ing.amount_in2 or 0,
        "amountOut2": ing.amount_out2 or 0,
        "amountIn3":  ing.amount_in3 or 0,
        "amountOut3": ing.amount_out3 or 0,
        "packageCount":  ing.package_count or 0,
        "packageTypeId": ing.package_type_id,
    }


def _build_new_chart_payload(
    chart: AssemblyChart,
    ingredients: list[ChartIngredient],
    effective_date: str,
) -> dict:
    """
    Строит JSON для POST /assemblyCharts/save — СОЗДАНИЕ новой техкарты.
    БЕЗ поля 'id' — IIKO создаёт новую с dateFrom=effective_date.
    IIKO автоматически закрывает предыдущую (ставит ей dateTo=effective_date).
    """
    try:
        departments = json.loads(chart.direct_writeoff_departments or "[]")
    except Exception:
        departments = []

    return {
        # id НЕ передаём — это создание, а не обновление
        "assembledProductId": chart.dish.iiko_uuid,
        "dateFrom": effective_date,        # с какой даты действует новая версия
        "dateTo": None,                    # бессрочно (последняя версия)
        "assembledAmount": chart.assembled_amount,
        "productWriteoffStrategy": chart.writeoff_strategy or "ASSEMBLE",
        "effectiveDirectWriteoffStoreSpecification": {
            "departments": departments,
            "inverse": chart.direct_writeoff_inverse if chart.direct_writeoff_inverse is not None else True,
        },
        "productSizeAssemblyStrategy": chart.size_assembly_strategy or "COMMON",
        "items": [
            {**_ingredient_to_iiko_item(ing), "sortWeight": float(idx)}
            for idx, ing in enumerate(sorted(ingredients, key=lambda x: x.sort_weight))
        ],
        "technologyDescription": chart.technology_description or "",
        "description": chart.description or "",
        "appearance": chart.appearance or "",
        "organoleptic": chart.organoleptic or "",
        "outputComment": chart.output_comment or "",
    }


def _resync_dish(db: Session, restaurant, dish: Dish, name_map: dict) -> None:
    """
    Пересинхронизирует все техкарты одного блюда из IIKO (после изменения).
    Использует getHistory чтобы получить актуальные версии с правильными dateTo.
    Удаляет из БД версии которых больше нет в IIKO (например удалённые нами для отката).
    """
    from datetime import datetime, timezone
    synced_at = datetime.now(timezone.utc)

    history = iiko_svc.fetch_chart_history(db, restaurant, dish.iiko_uuid)
    if not history:
        return

    # UUID всех версий которые сейчас есть в IIKO
    iiko_uuids = {h.get("id") for h in history if h.get("id")}

    # Удаляем из БД версии которых больше нет в IIKO
    db_charts = db.query(AssemblyChart).filter(
        AssemblyChart.dish_id == dish.id,
        AssemblyChart.restaurant_id == dish.restaurant_id,
    ).all()
    for db_chart in db_charts:
        if db_chart.iiko_uuid not in iiko_uuids:
            db.delete(db_chart)
    db.flush()

    for chart_data in history:
        chart_uuid = chart_data.get("id", "")
        if not chart_uuid:
            continue

        date_from_str = chart_data.get("dateFrom")
        date_to_str   = chart_data.get("dateTo")
        spec = chart_data.get("effectiveDirectWriteoffStoreSpecification") or {}

        chart = (
            db.query(AssemblyChart)
            .filter(AssemblyChart.restaurant_id == dish.restaurant_id, AssemblyChart.iiko_uuid == chart_uuid)
            .first()
        )
        if not chart:
            chart = AssemblyChart(
                restaurant_id=dish.restaurant_id,
                iiko_uuid=chart_uuid,
                dish_id=dish.id,
            )
            db.add(chart)

        chart.date_from = date.fromisoformat(date_from_str) if date_from_str else date(2020, 1, 1)
        chart.date_to   = date.fromisoformat(date_to_str) if date_to_str else None
        chart.assembled_amount  = chart_data.get("assembledAmount") or 1.0
        chart.writeoff_strategy = chart_data.get("productWriteoffStrategy") or "ASSEMBLE"
        chart.size_assembly_strategy = chart_data.get("productSizeAssemblyStrategy") or "COMMON"
        chart.direct_writeoff_departments = json.dumps(spec.get("departments") or [])
        chart.direct_writeoff_inverse     = spec.get("inverse", True)
        chart.technology_description = chart_data.get("technologyDescription")
        chart.description  = chart_data.get("description")
        chart.appearance   = chart_data.get("appearance")
        chart.organoleptic = chart_data.get("organoleptic")
        chart.output_comment = chart_data.get("outputComment")
        chart.synced_at = synced_at
        db.flush()

        # Пересоздаём ингредиенты
        db.query(ChartIngredient).filter(ChartIngredient.chart_id == chart.id).delete()
        for item in chart_data.get("items") or []:
            ing_uuid = (item.get("productId") or "").lower()
            if not ing_uuid:
                continue
            item_spec = item.get("storeSpecification")
            db.add(ChartIngredient(
                chart_id=chart.id,
                iiko_item_uuid=item.get("id"),
                ingredient_iiko_uuid=ing_uuid,
                ingredient_name=name_map.get(ing_uuid),
                sort_weight=item.get("sortWeight") or 0.0,
                store_departments=json.dumps(item_spec.get("departments") or []) if item_spec else None,
                store_inverse=item_spec.get("inverse") if item_spec else None,
                product_size_spec_id=item.get("productSizeSpecification"),
                amount_in=item.get("amountIn") or 0.0,
                amount_middle=item.get("amountMiddle"),
                amount_out=item.get("amountOut"),
                amount_in1=item.get("amountIn1") or 0.0,
                amount_out1=item.get("amountOut1") or 0.0,
                amount_in2=item.get("amountIn2") or 0.0,
                amount_out2=item.get("amountOut2") or 0.0,
                amount_in3=item.get("amountIn3") or 0.0,
                amount_out3=item.get("amountOut3") or 0.0,
                package_count=item.get("packageCount") or 0.0,
                package_type_id=item.get("packageTypeId"),
            ))
        db.flush()


def _get_name_map(db: Session) -> dict:
    """UUID → name из product_catalog (для кеша имён при ресинке)."""
    rows = db.query(ProductCatalog.product_iiko_id, ProductCatalog.name).all()
    return {r.product_iiko_id: r.name for r in rows}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/sync/{restaurant_id}")
def sync_charts(
    restaurant_id: int,
    body: SyncRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Синхронизировать техкарты из IIKO в нашу БД.
    Загружает все техкарты за период, кеширует блюда и ингредиенты.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    date_to = body.date_to or date.today().isoformat()

    # 1. Загрузить список продуктов для получения имён
    products_raw = iiko_svc.fetch_products_list(db, restaurant)
    name_map: dict[str, str] = {}
    for p in products_raw:
        uid = (p.get("id") or "").lower()
        if uid:
            name_map[uid] = p.get("name") or p.get("code") or uid

    # 2. Загрузить техкарты из IIKO
    charts_raw = iiko_svc.fetch_assembly_charts(db, restaurant, body.date_from, date_to)

    synced_at = datetime.now(timezone.utc)
    charts_created = 0
    charts_updated = 0
    ingredients_total = 0

    for chart_data in charts_raw:
        chart_uuid = chart_data.get("id", "")
        product_uuid = (chart_data.get("assembledProductId") or "").lower()

        if not chart_uuid or not product_uuid:
            continue

        # 3. Upsert блюда
        dish = (
            db.query(Dish)
            .filter(Dish.restaurant_id == restaurant_id, Dish.iiko_uuid == product_uuid)
            .first()
        )
        if not dish:
            dish = Dish(
                restaurant_id=restaurant_id,
                iiko_uuid=product_uuid,
                name=name_map.get(product_uuid),
                synced_at=synced_at,
            )
            db.add(dish)
            db.flush()
        elif not dish.name and product_uuid in name_map:
            dish.name = name_map[product_uuid]
            dish.synced_at = synced_at

        # 4. Upsert техкарты
        chart = (
            db.query(AssemblyChart)
            .filter(AssemblyChart.restaurant_id == restaurant_id, AssemblyChart.iiko_uuid == chart_uuid)
            .first()
        )

        date_from_str = chart_data.get("dateFrom")
        date_to_str = chart_data.get("dateTo")
        spec = chart_data.get("effectiveDirectWriteoffStoreSpecification") or {}

        if not chart:
            chart = AssemblyChart(
                restaurant_id=restaurant_id,
                iiko_uuid=chart_uuid,
                dish_id=dish.id,
            )
            db.add(chart)
            charts_created += 1
        else:
            charts_updated += 1

        chart.date_from = date.fromisoformat(date_from_str) if date_from_str else date(2020, 1, 1)
        chart.date_to = date.fromisoformat(date_to_str) if date_to_str else None
        chart.assembled_amount = chart_data.get("assembledAmount") or 1.0
        chart.writeoff_strategy = chart_data.get("productWriteoffStrategy") or "ASSEMBLE"
        chart.size_assembly_strategy = chart_data.get("productSizeAssemblyStrategy") or "COMMON"
        chart.direct_writeoff_departments = json.dumps(spec.get("departments") or [])
        chart.direct_writeoff_inverse = spec.get("inverse", True)
        chart.technology_description = chart_data.get("technologyDescription")
        chart.description = chart_data.get("description")
        chart.appearance = chart_data.get("appearance")
        chart.organoleptic = chart_data.get("organoleptic")
        chart.output_comment = chart_data.get("outputComment")
        chart.synced_at = synced_at

        db.flush()

        # 5. Пересинхронизировать ингредиенты: удалить старые, добавить новые
        db.query(ChartIngredient).filter(ChartIngredient.chart_id == chart.id).delete()

        for item in chart_data.get("items") or []:
            ing_uuid = (item.get("productId") or "").lower()
            if not ing_uuid:
                continue

            ing_name = name_map.get(ing_uuid)

            item_store_spec = item.get("storeSpecification")
            store_depts = None
            store_inv = None
            if item_store_spec:
                store_depts = json.dumps(item_store_spec.get("departments") or [])
                store_inv = item_store_spec.get("inverse")

            ing = ChartIngredient(
                chart_id=chart.id,
                iiko_item_uuid=item.get("id"),
                ingredient_iiko_uuid=ing_uuid,
                ingredient_name=ing_name,
                sort_weight=item.get("sortWeight") or 0.0,
                store_departments=store_depts,
                store_inverse=store_inv,
                product_size_spec_id=item.get("productSizeSpecification"),
                amount_in=item.get("amountIn") or 0.0,
                amount_middle=item.get("amountMiddle"),
                amount_out=item.get("amountOut"),
                amount_in1=item.get("amountIn1") or 0.0,
                amount_out1=item.get("amountOut1") or 0.0,
                amount_in2=item.get("amountIn2") or 0.0,
                amount_out2=item.get("amountOut2") or 0.0,
                amount_in3=item.get("amountIn3") or 0.0,
                amount_out3=item.get("amountOut3") or 0.0,
                package_count=item.get("packageCount") or 0.0,
                package_type_id=item.get("packageTypeId"),
            )
            db.add(ing)
            ingredients_total += 1

    # Связываем ингредиенты с product_catalog по UUID (мягкий FK)
    from sqlalchemy import text
    db.execute(
        text("""
        UPDATE chart_ingredients ci
        SET product_catalog_id = pc.id
        FROM assembly_charts ac, product_catalog pc
        WHERE ci.chart_id = ac.id
          AND pc.product_iiko_id = ci.ingredient_iiko_uuid
          AND ac.restaurant_id = :rid
          AND ci.product_catalog_id IS NULL
        """),
        {"rid": restaurant_id},
    )

    db.commit()

    linked = db.query(ChartIngredient).join(AssemblyChart).filter(
        AssemblyChart.restaurant_id == restaurant_id,
        ChartIngredient.product_catalog_id.isnot(None),
    ).count()

    return {
        "ok": True,
        "charts_created": charts_created,
        "charts_updated": charts_updated,
        "ingredients_total": ingredients_total,
        "ingredients_linked_to_catalog": linked,
        "dishes_total": db.query(Dish).filter(Dish.restaurant_id == restaurant_id).count(),
    }


@router.get("/dishes")
def list_dishes(
    restaurant_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Список всех блюд с количеством техкарт и ингредиентов."""
    dishes = db.query(Dish).filter(Dish.restaurant_id == restaurant_id).order_by(Dish.name).all()

    result = []
    for dish in dishes:
        active_chart = None
        today = date.today()
        for c in dish.charts:
            if c.date_from <= today and (c.date_to is None or c.date_to > today):
                active_chart = c
                break

        result.append({
            "id": dish.id,
            "iiko_uuid": dish.iiko_uuid,
            "name": dish.name,
            "charts_count": len(dish.charts),
            "ingredients_count": len(active_chart.ingredients) if active_chart else 0,
            "active_chart_id": active_chart.id if active_chart else None,
        })

    return result


@router.get("/search")
def search_by_ingredient(
    restaurant_id: int,
    ingredient: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Найти все техкарты, содержащие ингредиент (поиск по имени или UUID).
    Возвращает список блюд с активными техкартами содержащими этот ингредиент.
    """
    today = date.today()

    # Ищем ингредиенты по имени (ILIKE) или точному UUID
    query = (
        db.query(ChartIngredient)
        .join(AssemblyChart)
        .join(Dish)
        .filter(
            AssemblyChart.restaurant_id == restaurant_id,
            AssemblyChart.date_from <= today,
            (AssemblyChart.date_to == None) | (AssemblyChart.date_to > today),
        )
    )

    if len(ingredient) == 36 and "-" in ingredient:
        # UUID поиск
        query = query.filter(
            ChartIngredient.ingredient_iiko_uuid == ingredient.lower()
        )
    else:
        # Поиск по имени
        query = query.filter(
            ChartIngredient.ingredient_name.ilike(f"%{ingredient}%")
        )

    rows = query.all()

    # Группируем по блюду
    seen_charts: dict[int, dict] = {}
    for ing in rows:
        chart = ing.chart
        dish = chart.dish
        if chart.id not in seen_charts:
            seen_charts[chart.id] = {
                "chart_id": chart.id,
                "dish_id": dish.id,
                "dish_name": dish.name,
                "dish_iiko_uuid": dish.iiko_uuid,
                "date_from": chart.date_from.isoformat(),
                "date_to": chart.date_to.isoformat() if chart.date_to else None,
                "matched_ingredients": [],
            }
        seen_charts[chart.id]["matched_ingredients"].append({
            "ingredient_id": ing.id,
            "ingredient_iiko_uuid": ing.ingredient_iiko_uuid,
            "ingredient_name": ing.ingredient_name,
            "amount_in": ing.amount_in,
        })

    return list(seen_charts.values())


@router.get("/{chart_id}")
def get_chart(
    chart_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Полная техкарта с ингредиентами."""
    chart = db.query(AssemblyChart).filter(AssemblyChart.id == chart_id).first()
    if not chart:
        raise HTTPException(404, "Техкарта не найдена")

    return {
        "id": chart.id,
        "iiko_uuid": chart.iiko_uuid,
        "dish_name": chart.dish.name,
        "dish_iiko_uuid": chart.dish.iiko_uuid,
        "date_from": chart.date_from.isoformat(),
        "date_to": chart.date_to.isoformat() if chart.date_to else None,
        "assembled_amount": chart.assembled_amount,
        "writeoff_strategy": chart.writeoff_strategy,
        "synced_at": chart.synced_at.isoformat() if chart.synced_at else None,
        "ingredients": [
            {
                "id": ing.id,
                "iiko_item_uuid": ing.iiko_item_uuid,
                "ingredient_iiko_uuid": ing.ingredient_iiko_uuid,
                "ingredient_name": ing.ingredient_name,
                "sort_weight": ing.sort_weight,
                "amount_in": ing.amount_in,
                "amount_middle": ing.amount_middle,
                "amount_out": ing.amount_out,
            }
            for ing in sorted(chart.ingredients, key=lambda x: x.sort_weight)
        ],
    }


def _snapshot_chart(chart: AssemblyChart) -> dict:
    """Снапшот техкарты (блюдо + ингредиенты) для лога отката."""
    return {
        "chart_id": chart.id,
        "iiko_uuid": chart.iiko_uuid,
        "dish_id": chart.dish_id,
        "dish_name": chart.dish.name if chart.dish else None,
        "date_from": chart.date_from.isoformat() if chart.date_from else None,
        "date_to": chart.date_to.isoformat() if chart.date_to else None,
        "assembled_amount": chart.assembled_amount,
        "writeoff_strategy": chart.writeoff_strategy,
        "size_assembly_strategy": chart.size_assembly_strategy,
        "direct_writeoff_departments": chart.direct_writeoff_departments,
        "direct_writeoff_inverse": chart.direct_writeoff_inverse,
        "ingredients": [
            {
                "ingredient_iiko_uuid": ing.ingredient_iiko_uuid,
                "ingredient_name": ing.ingredient_name,
                "sort_weight": ing.sort_weight,
                "amount_in": ing.amount_in,
                "amount_middle": ing.amount_middle,
                "amount_out": ing.amount_out,
                "amount_in1": ing.amount_in1,
                "amount_out1": ing.amount_out1,
                "amount_in2": ing.amount_in2,
                "amount_out2": ing.amount_out2,
                "amount_in3": ing.amount_in3,
                "amount_out3": ing.amount_out3,
                "package_count": ing.package_count,
                "package_type_id": ing.package_type_id,
                "product_size_spec_id": ing.product_size_spec_id,
                "store_departments": ing.store_departments,
                "store_inverse": ing.store_inverse,
            }
            for ing in sorted(chart.ingredients, key=lambda x: x.sort_weight)
        ],
    }


def _run_bulk_op(
    db: Session,
    restaurant,
    chart_ids: list[int],
    restaurant_id: int,
    effective_date: str,
    modify_fn,  # callable(ingredients: list[ChartIngredient]) -> list[ChartIngredient] | None
    operation_type: str = "bulk_op",
    description: str = "",
    performed_by: str = "",
) -> list[dict]:
    """
    Общий runner для всех bulk-операций:
    1. Берёт текущую активную техкарту
    2. Применяет modify_fn к её ингредиентам (возвращает изменённый список)
    3. Создаёт НОВУЮ техкарту в IIKO (без id, с dateFrom=effective_date)
    4. IIKO автоматически закрывает старую (ставит ей dateTo)
    5. Пересинхронизирует блюдо из IIKO чтобы наша БД была актуальной
    6. Сохраняет снапшот в RecipeChangeLog для возможного отката
    """
    import time
    from datetime import date as date_type
    name_map = _get_name_map(db)
    results = []
    snapshots = []  # снапшоты для лога

    for chart_id in chart_ids:
        chart = (
            db.query(AssemblyChart)
            .filter(AssemblyChart.id == chart_id, AssemblyChart.restaurant_id == restaurant_id)
            .first()
        )
        if not chart:
            results.append({"chart_id": chart_id, "ok": False, "error": "техкарта не найдена"})
            continue

        # Пропускаем только SPECIFIC (своя норма на каждый размер) — там нельзя менять без потери данных
        if chart.size_assembly_strategy == "SPECIFIC":
            results.append({"chart_id": chart_id, "ok": True, "skipped": True,
                            "dish_name": chart.dish.name, "note": "шкала размеров — пропущено"})
            continue

        # Получаем текущие ингредиенты, применяем функцию изменения
        ingredients = sorted(chart.ingredients, key=lambda x: x.sort_weight)
        modified = modify_fn(list(ingredients))

        if modified is None:
            # modify_fn вернула None = ингредиент не найден, пропускаем
            results.append({"chart_id": chart_id, "ok": True, "skipped": True,
                            "dish_name": chart.dish.name, "note": "ингредиент не найден в этой карте"})
            continue

        # Снапшот ДО изменения (для отката)
        snap = _snapshot_chart(chart)

        try:
            # Строим payload для СОЗДАНИЯ новой техкарты (без id!)
            payload = _build_new_chart_payload(chart, modified, effective_date)
            iiko_svc.save_assembly_chart(db, restaurant, payload)

            # Пересинхронизируем блюдо из IIKO (получаем актуальные dateTo у старой + новая)
            _resync_dish(db, restaurant, chart.dish, name_map)
            db.flush()

            snapshots.append(snap)
            results.append({
                "chart_id": chart_id,
                "ok": True,
                "dish_name": chart.dish.name,
                "effective_date": effective_date,
            })
        except Exception as e:
            results.append({"chart_id": chart_id, "ok": False, "error": str(e),
                            "dish_name": chart.dish.name})

        # Пауза между запросами чтобы не перегружать IIKO сервер
        time.sleep(0.3)

    # Сохраняем лог если были успешные изменения
    if snapshots:
        try:
            eff_date = date_type.fromisoformat(effective_date)
        except Exception:
            eff_date = date_type.today()
        log_entry = RecipeChangeLog(
            restaurant_id=restaurant_id,
            operation_type=operation_type,
            performed_by=performed_by,
            effective_date=eff_date,
            description=description,
            snapshot=json.dumps(snapshots, ensure_ascii=False),
            is_rolled_back=False,
        )
        db.add(log_entry)

    db.commit()
    return results


@router.post("/bulk-remove-ingredient")
def bulk_remove_ingredient(
    body: BulkRemoveRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Удалить ингредиент из нескольких техкарт.
    Создаёт НОВУЮ версию техкарты в IIKO начиная с effective_date (default: сегодня).
    Старая версия остаётся в истории. IIKO автоматически закрывает её.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    effective_date = body.effective_date or date.today().isoformat()
    iiko_uuid_lower = body.ingredient_iiko_uuid.lower()

    def remove_ingredient(ingredients: list[ChartIngredient]):
        filtered = [i for i in ingredients if i.ingredient_iiko_uuid != iiko_uuid_lower]
        if len(filtered) == len(ingredients):
            return None  # не нашли ингредиент
        return filtered

    # Ищем имя ингредиента для описания в логе
    sample_chart = db.query(AssemblyChart).filter(
        AssemblyChart.id.in_(body.chart_ids)
    ).first()
    ing_name = next(
        (i.ingredient_name for i in (sample_chart.ingredients if sample_chart else [])
         if i.ingredient_iiko_uuid == iiko_uuid_lower),
        body.ingredient_iiko_uuid,
    )

    results = _run_bulk_op(
        db, restaurant, body.chart_ids, body.restaurant_id, effective_date, remove_ingredient,
        operation_type="bulk_remove",
        description=f"Удалён ингредиент: {ing_name}",
        performed_by=current_user.username,
    )
    ok_count = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    return {"total": len(body.chart_ids), "ok": ok_count,
            "failed": sum(1 for r in results if not r.get("ok")),
            "effective_date": effective_date, "results": results}


@router.post("/bulk-replace-ingredient")
def bulk_replace_ingredient(
    body: BulkReplaceRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Заменить один ингредиент на другой в нескольких техкартах.
    Можно менять UUID (сам продукт) и/или количество.
    Создаёт НОВУЮ версию техкарты начиная с effective_date.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    effective_date = body.effective_date or date.today().isoformat()
    old_uuid = body.old_ingredient_uuid.lower()
    new_uuid = body.new_ingredient_uuid.lower()

    def replace_ingredient(ingredients: list[ChartIngredient]):
        found = False
        result = []
        for ing in ingredients:
            if ing.ingredient_iiko_uuid == old_uuid:
                found = True
                # Создаём "виртуальный" объект с новыми значениями (не сохраняем в БД)
                from copy import copy
                new_ing = copy(ing)
                new_ing.ingredient_iiko_uuid = new_uuid
                new_ing.ingredient_name = body.new_ingredient_name
                new_ing.amount_in     = body.new_amount_in
                new_ing.amount_middle = body.new_amount_middle or body.new_amount_in
                new_ing.amount_out    = body.new_amount_out or body.new_amount_in
                result.append(new_ing)
            else:
                result.append(ing)
        return result if found else None

    old_name = next(
        (i.ingredient_name for chart in db.query(AssemblyChart).filter(AssemblyChart.id.in_(body.chart_ids)).all()
         for i in chart.ingredients if i.ingredient_iiko_uuid == old_uuid),
        old_uuid,
    )
    new_name = body.new_ingredient_name or new_uuid

    results = _run_bulk_op(
        db, restaurant, body.chart_ids, body.restaurant_id, effective_date, replace_ingredient,
        operation_type="bulk_replace",
        description=f"Замена: {old_name} → {new_name} ({body.new_amount_in})",
        performed_by=current_user.username,
    )
    ok_count = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    return {"total": len(body.chart_ids), "ok": ok_count,
            "failed": sum(1 for r in results if not r.get("ok")),
            "effective_date": effective_date, "results": results}


@router.post("/bulk-update-amount")
def bulk_update_ingredient_amount(
    body: BulkUpdateAmountRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Изменить количество (брутто) ингредиента в нескольких техкартах.
    Создаёт НОВУЮ версию техкарты начиная с effective_date.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    effective_date = body.effective_date or date.today().isoformat()
    iiko_uuid_lower = body.ingredient_iiko_uuid.lower()

    def update_amount(ingredients: list[ChartIngredient]):
        found = False
        from copy import copy
        result = []
        for ing in ingredients:
            if ing.ingredient_iiko_uuid == iiko_uuid_lower:
                found = True
                new_ing = copy(ing)
                new_ing.amount_in     = body.new_amount_in
                new_ing.amount_middle = body.new_amount_in
                new_ing.amount_out    = body.new_amount_in
                result.append(new_ing)
            else:
                result.append(ing)
        return result if found else None

    sample = db.query(AssemblyChart).filter(AssemblyChart.id.in_(body.chart_ids)).first()
    ing_name = next(
        (i.ingredient_name for i in (sample.ingredients if sample else [])
         if i.ingredient_iiko_uuid == iiko_uuid_lower),
        iiko_uuid_lower,
    )

    results = _run_bulk_op(
        db, restaurant, body.chart_ids, body.restaurant_id, effective_date, update_amount,
        operation_type="bulk_update_amount",
        description=f"Изменено количество: {ing_name} → {body.new_amount_in}",
        performed_by=current_user.username,
    )
    ok_count = sum(1 for r in results if r.get("ok") and not r.get("skipped"))
    return {"total": len(body.chart_ids), "ok": ok_count,
            "failed": sum(1 for r in results if not r.get("ok")),
            "effective_date": effective_date, "results": results}


class RestoreChartRequest(BaseModel):
    restaurant_id: int
    chart_ids: list[int]   # ID техкарт в нашей БД которые нужно удалить из IIKO (откат)


@router.post("/restore-charts")
def restore_charts(
    body: RestoreChartRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Удалить указанные версии техкарт из IIKO (откат).
    IIKO автоматически активирует предыдущую версию (от shama/до нашего изменения).
    Используется для восстановления блюд со шкалой размеров которые были повреждены.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    name_map = _get_name_map(db)
    results = []

    for chart_id in body.chart_ids:
        chart = (
            db.query(AssemblyChart)
            .filter(AssemblyChart.id == chart_id, AssemblyChart.restaurant_id == body.restaurant_id)
            .first()
        )
        if not chart:
            results.append({"chart_id": chart_id, "ok": False, "error": "техкарта не найдена"})
            continue

        try:
            ok = iiko_svc.delete_assembly_chart(db, restaurant, chart.iiko_uuid)
            if ok:
                # Пересинхронизируем блюдо (обновляем нашу БД)
                _resync_dish(db, restaurant, chart.dish, name_map)
                db.flush()
                results.append({"chart_id": chart_id, "ok": True, "dish_name": chart.dish.name})
            else:
                results.append({"chart_id": chart_id, "ok": False,
                                "dish_name": chart.dish.name, "error": "IIKO отказал в удалении"})
        except Exception as e:
            results.append({"chart_id": chart_id, "ok": False,
                            "dish_name": chart.dish.name, "error": str(e)})

    db.commit()
    ok_count = sum(1 for r in results if r.get("ok"))
    return {"total": len(body.chart_ids), "ok": ok_count,
            "failed": sum(1 for r in results if not r.get("ok")),
            "results": results}


# ─── Excel Import ──────────────────────────────────────────────────────────────

@router.post("/import-excel")
def import_recipes_from_excel(
    file: UploadFile = File(...),
    restaurant_id: int = Form(...),
    effective_date: str = Form(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Импорт рецептур из Excel-файла.
    Ожидаемые столбцы (порядок или названия):
      - Код блюда   (product_num блюда,  напр. "3030")
      - Код товара  (product_num товара, напр. "0016")
      - Фактор      (количество брутто,  напр. 0.15)
    Опционально:
      - Название блюда, Название товара, Ед. измерения (для справки)

    Алгоритм:
    1. Парсит Excel
    2. Ищет блюдо по коду в таблице dishes (name ILIKE 'КОД.%' или 'КОД %')
    3. Ищет товар по коду в product_catalog (product_num)
    4. Группирует строки по блюду → строит список ингредиентов
    5. Создаёт новую версию техкарты в IIKO через save
    """
    import io, time
    import openpyxl

    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")

    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    eff_date = effective_date or date.today().isoformat()

    # ── Читаем Excel ──────────────────────────────────────────────────────────
    try:
        wb = openpyxl.load_workbook(io.BytesIO(file.file.read()), data_only=True)
        ws = wb.active
    except Exception as e:
        raise HTTPException(400, f"Не удалось прочитать Excel: {e}")

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        raise HTTPException(400, "Файл пустой или содержит только заголовок")

    def _cell(row, idx):
        v = row[idx] if idx < len(row) else None
        return str(v).strip() if v is not None and str(v).strip() not in ("None", "") else ""

    def _to_float(v) -> float | None:
        if v is None:
            return None
        try:
            return float(str(v).replace(",", ".").strip())
        except ValueError:
            return None

    # ── Кеши ──────────────────────────────────────────────────────────────────
    catalog_rows = db.query(
        ProductCatalog.product_num,
        ProductCatalog.product_iiko_id,
        ProductCatalog.name,
        ProductCatalog.unit_type,
    ).filter(ProductCatalog.is_deleted == False).all()

    catalog_by_code: dict[str, tuple] = {}
    for r in catalog_rows:
        if r.product_num:
            catalog_by_code[r.product_num.strip().upper()] = (r.product_iiko_id, r.name, r.unit_type)

    all_dishes = db.query(Dish).filter(Dish.restaurant_id == restaurant_id).all()
    dish_by_code: dict[str, Dish] = {}
    for d in all_dishes:
        if d.name:
            prefix = d.name.split(".")[0].split(" ")[0].strip().upper()
            if prefix:
                dish_by_code[prefix] = d

    # ── Конвертация единиц: г/мл → кг/л (делим на 1000) ─────────────────────
    DIVIDE_BY_1000 = {"г", "г.", "гр", "гр.", "g", "мл", "мл.", "ml"}

    def convert_factor(factor: float, unit: str) -> float:
        if unit.lower().strip() in DIVIDE_BY_1000:
            return round(factor / 1000, 6)
        return factor

    # ── Парсим строки ─────────────────────────────────────────────────────────
    # Формат из IIKO-экспорта (сгруппированный):
    #   Строка-заголовок:   "Изменение состава..."  → пропускаем
    #   Строка-блюдо:       Название | КОД(число) | "Артикул" | "Ед изм" | "Фактор"
    #   Строки-ингредиенты: Название | (пусто)    | Артикул   | Ед изм   | Фактор(число)
    #
    # Признак строки-блюда:  col1 — целое число (код блюда)
    # Признак строки-ингред: col1 пустой, col2 — артикул, col4 — число
    from collections import defaultdict
    dish_ingredients: dict[str, list[dict]] = defaultdict(list)
    parse_errors: list[str] = []

    LABEL_WORDS = {"артикул", "ед изм", "фактор", "ед.", "изм", "количество", "наименование", "название"}

    def _is_label_row(row) -> bool:
        """Строка содержит только текстовые заголовки столбцов."""
        texts = [_cell(row, i).lower() for i in range(min(len(row), 6))]
        return any(w in " ".join(texts) for w in LABEL_WORDS) and _to_float(row[4] if len(row) > 4 else None) is None

    def _is_numeric_code(s: str) -> bool:
        """Строка — числовой код блюда (целое число, возможно с пробелами)."""
        return s.replace(" ", "").isdigit()

    current_dish_code: str | None = None

    for row_num, row in enumerate(rows, start=1):
        if not any(c for c in row):
            continue  # пустая строка

        col0 = _cell(row, 0)
        col1 = _cell(row, 1)  # код блюда (число) или пусто
        col2 = _cell(row, 2)  # артикул товара
        col3 = _cell(row, 3)  # ед. измерения
        col4_raw = row[4] if len(row) > 4 else None

        # Пропускаем заголовочные строки (название таблицы, заголовки столбцов)
        if _is_label_row(row):
            continue
        if col0 and not col1 and not col2:
            # Строка только с текстом в col0 — скорее всего заголовок таблицы
            continue

        # ── Строка-блюдо: col1 = числовой код ────────────────────────────
        if col1 and _is_numeric_code(col1):
            current_dish_code = col1.strip().upper()
            continue

        # ── Строка-ингредиент: col1 пуст, col2 = артикул, col4 = число ───
        if not col1 and col2 and col4_raw is not None and current_dish_code:
            product_code = col2.upper()
            unit_raw     = col3.strip() if col3 else ""
            factor_val   = _to_float(col4_raw)

            # Пропускаем строки где col2 — текстовый заголовок
            if col2.lower() in LABEL_WORDS:
                continue

            if factor_val is None:
                parse_errors.append(f"Строка {row_num}: некорректный фактор '{col4_raw}' (артикул {product_code})")
                continue
            if factor_val <= 0:
                parse_errors.append(f"Строка {row_num}: фактор должен быть > 0 (артикул {product_code})")
                continue

            # г → кг, мл → л
            amount_iiko = convert_factor(factor_val, unit_raw)

            # Ищем товар (пробуем с дефисами и без ведущих нулей)
            product = (
                catalog_by_code.get(product_code)
                or catalog_by_code.get(product_code.replace("-", ""))
                or catalog_by_code.get(product_code.replace("/", ""))
                or catalog_by_code.get(product_code.lstrip("0"))
            )
            if not product:
                parse_errors.append(f"Строка {row_num}: артикул '{product_code}' не найден в каталоге (блюдо {current_dish_code})")
                continue

            product_uuid, product_name, _ = product
            dish_ingredients[current_dish_code].append({
                "product_uuid": product_uuid,
                "product_name": product_name,
                "unit_raw":     unit_raw,
                "amount_in":    amount_iiko,
                "amount_raw":   factor_val,
            })

    if not dish_ingredients:
        raise HTTPException(400, f"Нет данных для импорта. Ошибки: {'; '.join(parse_errors[:5])}")

    # ── Создаём техкарты в IIKO ───────────────────────────────────────────────
    name_map = _get_name_map(db)
    results = []

    for dish_code, ingredients in dish_ingredients.items():
        # Ищем блюдо
        dish = dish_by_code.get(dish_code)
        if not dish:
            results.append({
                "dish_code": dish_code, "ok": False,
                "error": f"Блюдо с кодом '{dish_code}' не найдено в БД (синхронизируйте техкарты)"
            })
            continue

        # Строим payload — создаём новую версию техкарты
        items = [
            {
                "sortWeight": float(idx),
                "productId": ing["product_uuid"],
                "productSizeSpecification": None,
                "storeSpecification": None,
                "amountIn":    ing["amount_in"],
                "amountMiddle": ing["amount_in"],
                "amountOut":   ing["amount_in"],
                "amountIn1": 0, "amountOut1": 0,
                "amountIn2": 0, "amountOut2": 0,
                "amountIn3": 0, "amountOut3": 0,
                "packageCount": 0,
                "packageTypeId": None,
            }
            for idx, ing in enumerate(ingredients)
        ]

        payload = {
            "assembledProductId": dish.iiko_uuid,
            "dateFrom": eff_date,
            "dateTo": None,
            "assembledAmount": 1.0,
            "productWriteoffStrategy": "ASSEMBLE",
            "effectiveDirectWriteoffStoreSpecification": {"departments": [], "inverse": False},
            "productSizeAssemblyStrategy": "COMMON",
            "items": items,
            "technologyDescription": "",
            "description": "",
            "appearance": "",
            "organoleptic": "",
            "outputComment": "",
        }

        try:
            iiko_svc.save_assembly_chart(db, restaurant, payload)
            _resync_dish(db, restaurant, dish, name_map)
            db.flush()
            results.append({
                "dish_code": dish_code,
                "dish_name": dish.name,
                "ok": True,
                "ingredients_count": len(ingredients),
            })
        except Exception as e:
            results.append({
                "dish_code": dish_code,
                "dish_name": dish.name,
                "ok": False,
                "error": str(e),
            })

        time.sleep(0.2)

    db.commit()

    ok_count     = sum(1 for r in results if r.get("ok"))
    failed_count = sum(1 for r in results if not r.get("ok"))

    return {
        "ok": ok_count,
        "failed": failed_count,
        "parse_errors": parse_errors,
        "effective_date": eff_date,
        "results": results,
    }


# ─── История изменений + Откат ─────────────────────────────────────────────────

@router.get("/change-log")
def get_change_log(
    restaurant_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Список bulk-изменений техкарт (для отображения истории и отката).
    Возвращает последние `limit` записей, отсортированных от новых к старым.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")

    logs = (
        db.query(RecipeChangeLog)
        .filter(RecipeChangeLog.restaurant_id == restaurant_id)
        .order_by(RecipeChangeLog.performed_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "operation_type": log.operation_type,
            "performed_at": log.performed_at.isoformat(),
            "performed_by": log.performed_by,
            "effective_date": log.effective_date.isoformat(),
            "description": log.description,
            "is_rolled_back": log.is_rolled_back,
            "dishes_count": len(json.loads(log.snapshot)) if log.snapshot else 0,
        }
        for log in logs
    ]


class RollbackRequest(BaseModel):
    rollback_date: Optional[str] = None  # дата с которой откатить; default = сегодня


@router.post("/rollback/{log_id}")
def rollback_change(
    log_id: int,
    body: RollbackRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Откат bulk-изменения:
    Для каждого блюда из снапшота создаёт новую версию техкарты в IIKO
    со старыми ингредиентами начиная с rollback_date.
    IIKO автоматически закрывает текущую (неправильную) версию.
    """
    if current_user.role not in ("admin", "co"):
        raise HTTPException(403, "Нет доступа")

    log = db.query(RecipeChangeLog).filter(RecipeChangeLog.id == log_id).first()
    if not log:
        raise HTTPException(404, "Запись лога не найдена")
    if log.is_rolled_back:
        raise HTTPException(400, "Это изменение уже было откачено")

    restaurant = db.query(Restaurant).filter(Restaurant.id == log.restaurant_id).first()
    if not restaurant:
        raise HTTPException(404, "Ресторан не найден")

    rollback_date = body.rollback_date or date.today().isoformat()
    snapshots = json.loads(log.snapshot)
    name_map = _get_name_map(db)
    results = []

    import time

    for snap in snapshots:
        dish_id = snap.get("dish_id")
        dish_name = snap.get("dish_name", "?")

        # Находим текущую активную техкарту для этого блюда
        today = date.today()
        current_chart = (
            db.query(AssemblyChart)
            .filter(
                AssemblyChart.dish_id == dish_id,
                AssemblyChart.restaurant_id == log.restaurant_id,
                AssemblyChart.date_from <= today,
                (AssemblyChart.date_to == None) | (AssemblyChart.date_to > today),
            )
            .first()
        )

        if not current_chart:
            results.append({"dish_name": dish_name, "ok": False, "error": "текущая техкарта не найдена"})
            continue

        # Строим payload из снапшота ингредиентов
        items = []
        for ing in snap.get("ingredients", []):
            items.append({
                "sortWeight": ing.get("sort_weight", 0),
                "productId": ing["ingredient_iiko_uuid"],
                "productSizeSpecification": ing.get("product_size_spec_id"),
                "storeSpecification": None,
                "amountIn":     ing["amount_in"],
                "amountMiddle": ing.get("amount_middle") or ing["amount_in"],
                "amountOut":    ing.get("amount_out") or ing["amount_in"],
                "amountIn1":    ing.get("amount_in1") or 0,
                "amountOut1":   ing.get("amount_out1") or 0,
                "amountIn2":    ing.get("amount_in2") or 0,
                "amountOut2":   ing.get("amount_out2") or 0,
                "amountIn3":    ing.get("amount_in3") or 0,
                "amountOut3":   ing.get("amount_out3") or 0,
                "packageCount":  ing.get("package_count") or 0,
                "packageTypeId": ing.get("package_type_id"),
            })

        spec = json.loads(current_chart.direct_writeoff_departments or "[]")
        payload = {
            "assembledProductId": current_chart.dish.iiko_uuid,
            "assembledAmount": current_chart.assembled_amount,
            "productWriteoffStrategy": current_chart.writeoff_strategy,
            "productSizeAssemblyStrategy": current_chart.size_assembly_strategy,
            "effectiveDirectWriteoffStoreSpecification": {
                "storeIds": spec,
                "inversed": current_chart.direct_writeoff_inverse,
            },
            "dateFrom": rollback_date,
            "technologyDescription": current_chart.technology_description or "",
            "description": current_chart.description or "",
            "appearance": current_chart.appearance or "",
            "organoleptic": current_chart.organoleptic or "",
            "outputComment": current_chart.output_comment or "",
            "items": items,
        }

        try:
            iiko_svc.save_assembly_chart(db, restaurant, payload)
            _resync_dish(db, restaurant, current_chart.dish, name_map)
            db.flush()
            results.append({"dish_name": dish_name, "ok": True, "rollback_date": rollback_date})
        except Exception as e:
            results.append({"dish_name": dish_name, "ok": False, "error": str(e)})

        time.sleep(0.3)

    ok_count = sum(1 for r in results if r.get("ok"))
    if ok_count > 0:
        log.is_rolled_back = True

    db.commit()

    return {
        "total": len(snapshots),
        "ok": ok_count,
        "failed": sum(1 for r in results if not r.get("ok")),
        "rollback_date": rollback_date,
        "results": results,
    }
