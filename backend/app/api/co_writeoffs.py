"""
CO Акт Списания.

GET  /api/co/writeoffs/load                         — дефицит из iiko OLAP inventory
GET  /api/co/writeoffs/                             — список актов
GET  /api/co/writeoffs/{id}                         — акт + позиции
POST /api/co/writeoffs/                             — создать акт
POST /api/co/writeoffs/{id}/post-to-iiko            — отправить в iiko
DELETE /api/co/writeoffs/history                    — очистить историю актов

GET  /api/co/writeoffs/settings/preset              — текущий UUID пресета
POST /api/co/writeoffs/settings/preset              — сохранить UUID пресета
POST /api/co/writeoffs/settings/preset/activate     — проверить пресет → вернуть колонки
POST /api/co/writeoffs/settings/sync-accounts       — синхронизировать счета из iiko
GET  /api/co/writeoffs/settings/accounts            — список счетов
DELETE /api/co/writeoffs/settings/accounts/{id}     — удалить счёт
GET  /api/co/writeoffs/settings/warehouse-types     — список типов складов
POST /api/co/writeoffs/settings/warehouse-types     — создать тип склада
PATCH /api/co/writeoffs/settings/warehouse-types/{id} — обновить тип склада
DELETE /api/co/writeoffs/settings/warehouse-types/{id} — удалить тип склада
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.co_auth import get_current_co_user, CoUser
from app.models.co_models import (
    CoRestaurant, CoWarehouse, CoProduct,
    CoAccount, CoProductGroup, CoProductGroupMember,
    CoWarehouseType,
    CoWriteoffAct, CoWriteoffItem, CoSetting,
)
from app.services.co_iiko import fetch_olap, post_writeoff as iiko_post_writeoff, _get_key

PRESET_KEY = "inventory_preset_id"

logger = logging.getLogger(__name__)


def _dt_iso(dt: Optional[datetime]) -> Optional[str]:
    """Возвращает ISO без таймзоны — чтобы браузер не конвертировал UTC в локальное."""
    if dt is None:
        return None
    return dt.replace(tzinfo=None).isoformat()
router = APIRouter(prefix="/api/co/writeoffs", tags=["co-writeoffs"])
# settings sub-router registered FIRST so /settings/* doesn't get caught by /{act_id}
_settings = APIRouter()


def _check_access(user: CoUser, restaurant_id: int) -> None:
    if user.role == "admin":
        return
    if restaurant_id not in [r.id for r in user.restaurants]:
        raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")


def _user_restaurant_ids(user: CoUser) -> list[int]:
    if user.role == "admin":
        return None  # None means all
    return [r.id for r in user.restaurants]


# ── Load inventory deficit from iiko OLAP ─────────────────────────────────────

@router.get("/load")
def load_inventory(
    date_from: str,  # YYYY-MM-DD
    date_to: str,    # YYYY-MM-DD
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """
    Тянет OLAP inventory пресет с chain-сервера (ресторан CO) одним запросом.
    Матчит строки по колонке Store → CoWarehouse.name → CoRestaurant.
    Счёт списания берётся из типа склада (warehouse_type.account).
    Возвращает дефицит по продуктам (Amount < 0).
    """
    preset_setting = db.query(CoSetting).filter(CoSetting.key == PRESET_KEY).first()
    preset_id = preset_setting.value if preset_setting else None
    if not preset_id:
        raise HTTPException(status_code=400, detail="Пресет инвентаризации не настроен.")

    # Chain-сервер — ресторан CO (https://original-group-co.iiko.it)
    chain_rest = (
        db.query(CoRestaurant).filter(CoRestaurant.code == "CO").first()
        or db.query(CoRestaurant).filter(CoRestaurant.is_active == True).first()
    )
    if not chain_rest:
        raise HTTPException(status_code=400, detail="Нет активных ресторанов")

    allowed_ids = _user_restaurant_ids(user)

    # Словарь: store_name.lower() → (CoWarehouse, CoRestaurant)
    wh_by_store: dict[str, tuple] = {}

    for rest in db.query(CoRestaurant).filter(
        CoRestaurant.is_active == True, CoRestaurant.code != "CO"
    ).all():
        if allowed_ids is not None and rest.id not in allowed_ids:
            continue
        for wh in db.query(CoWarehouse).filter(CoWarehouse.restaurant_id == rest.id).all():
            key = wh.name.strip().lower()
            if key not in wh_by_store:
                wh_by_store[key] = (wh, rest)

    all_products = [p for p in db.query(CoProduct).filter(CoProduct.is_active == True).all() if p.unit]
    products_by_num: dict[str, CoProduct] = {p.unit: p for p in all_products}
    # Для поиска по названию (запасной вариант когда артикулы расходятся)
    products_by_name: dict[str, CoProduct] = {}
    for p in db.query(CoProduct).filter(CoProduct.is_active == True).all():
        key = p.name.strip().lower()
        if key not in products_by_name:
            products_by_name[key] = p

    def _find_product(num: str, name: str = "") -> Optional[CoProduct]:
        """1) Точный артикул  2) Части составного  3) По названию."""
        if num in products_by_num:
            return products_by_num[num]
        for part in num.split("-"):
            part = part.strip()
            if part and part in products_by_num:
                return products_by_num[part]
        # Поиск по точному названию (CO сервер и точки могут иметь разные артикулы)
        if name:
            return products_by_name.get(name.strip().lower())
        return None

    try:
        olap_rows = fetch_olap(chain_rest, preset_id, date_from, date_to)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"iiko ошибка: {e}")

    rows = []
    errors = []
    no_type_warned: set[int] = set()
    missing_products: dict[str, dict] = {}  # num → {name, sum} для ненайденных

    for row in olap_rows:
        store_name = str(row.get("Store") or "").strip()
        match = wh_by_store.get(store_name.lower())
        if not match:
            continue
        warehouse, rest = match

        product_num = str(row.get("Product.Num") or "").strip()
        if not product_num:
            continue
        amount_raw = row.get("Amount") or row.get("amount") or 0
        try:
            amount = float(str(amount_raw).replace(",", "."))
        except (ValueError, TypeError):
            continue

        if amount >= 0:
            continue

        product_name_olap = str(row.get("Product.Name") or "").strip()
        product = _find_product(product_num, product_name_olap)
        if not product:
            # Копим ненайденные — покажем в errors с суммой
            key = f"{store_name}|{product_num}"
            if key not in missing_products:
                missing_products[key] = {
                    "store": store_name,
                    "restaurant_name": rest.name,
                    "num": product_num,
                    "name": str(row.get("Product.Name") or ""),
                    "amount": 0.0,
                    "sum": 0.0,
                }
            missing_products[key]["amount"] += abs(amount)
            resigned_sum_raw2 = row.get("Sum.ResignedSum") or 0
            try:
                missing_products[key]["sum"] += abs(float(str(resigned_sum_raw2).replace(",", ".")))
            except (ValueError, TypeError):
                pass
            continue

        # Счёт берётся из типа склада
        wh_type = warehouse.warehouse_type if warehouse.warehouse_type_id else None
        account = wh_type.account if wh_type else None

        if not wh_type and warehouse.id not in no_type_warned:
            errors.append({
                "restaurant_name": rest.name,
                "error": f"Склад «{warehouse.name}» не имеет типа — назначьте тип в Настройки → Склады.",
            })
            no_type_warned.add(warehouse.id)

        # Дата/время инвентаризации из OLAP
        inv_dt_raw = str(row.get("DateTime.DateTyped") or "").strip()
        inventory_datetime: Optional[datetime] = None
        has_time = False
        if inv_dt_raw:
            # Форматы с временем
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
                try:
                    inventory_datetime = datetime.strptime(inv_dt_raw, fmt)
                    has_time = True
                    break
                except ValueError:
                    continue
            # Форматы только дата
            if not inventory_datetime:
                for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
                    try:
                        inventory_datetime = datetime.strptime(inv_dt_raw[:10], fmt)
                        break
                    except ValueError:
                        continue

        # −2ч только если в OLAP есть реальное время, иначе оставляем None
        writeoff_datetime = (inventory_datetime - timedelta(hours=2)) if (inventory_datetime and has_time) else None

        # Сумма из OLAP (приходит отрицательной, как Amount)
        resigned_sum_raw = row.get("Sum.ResignedSum") or 0
        try:
            resigned_sum = abs(float(str(resigned_sum_raw).replace(",", ".")))
        except (ValueError, TypeError):
            resigned_sum = 0.0

        rows.append({
            "restaurant_id": rest.id,
            "restaurant_name": rest.name,
            "warehouse_id": warehouse.id,
            "warehouse_name": warehouse.name,
            "warehouse_iiko_id": warehouse.iiko_store_id,
            "warehouse_type": wh_type.name if wh_type else None,
            "product_id": product.id,
            "product_name": product.name,
            "product_num": product_num,
            "amount": round(abs(amount), 3),
            "resigned_sum": round(resigned_sum, 2),
            "inventory_datetime": _dt_iso(inventory_datetime),
            "writeoff_datetime": _dt_iso(writeoff_datetime),
            "account_id": account.id if account else None,
            "account_name": account.name if account else None,
            "account_iiko_id": account.account_iiko_id if account else None,
        })

    # Группируем ненайденные по ресторану
    if missing_products:
        by_rest_miss: dict[str, dict] = {}
        for v in missing_products.values():
            rn = v["restaurant_name"]
            if rn not in by_rest_miss:
                by_rest_miss[rn] = {"restaurant_name": rn, "items": [], "total_sum": 0.0}
            by_rest_miss[rn]["items"].append(f'{v["name"]} (арт. {v["num"]})')
            by_rest_miss[rn]["total_sum"] += v["sum"]
        for v in by_rest_miss.values():
            errors.append({
                "restaurant_name": v["restaurant_name"],
                "error": (
                    f"Не найдено в базе {len(v['items'])} товаров на сумму "
                    f"{v['total_sum']:,.0f} ₸ — нужна синхронизация продуктов: "
                    + ", ".join(v["items"][:5])
                    + (f" и ещё {len(v['items'])-5}" if len(v["items"]) > 5 else "")
                ),
                "missing_sum": round(v["total_sum"], 2),
            })

    return {"rows": rows, "errors": errors}


# ── Create act ────────────────────────────────────────────────────────────────

class WriteoffItemIn(BaseModel):
    restaurant_id: int
    warehouse_id: int
    product_id: int
    amount: float
    resigned_sum: Optional[float] = None       # Sum.ResignedSum из OLAP
    inventory_datetime: Optional[str] = None   # ISO datetime из OLAP
    writeoff_datetime: Optional[str] = None    # inventory_datetime - 2h


class CreateActRequest(BaseModel):
    act_date: str  # YYYY-MM-DD (fallback если нет writeoff_datetime)
    comment: Optional[str] = None
    items: list[WriteoffItemIn]


@router.post("/", status_code=201)
def create_acts(
    body: CreateActRequest,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    from collections import defaultdict

    try:
        act_date_obj = date.fromisoformat(body.act_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты (YYYY-MM-DD)")

    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d", "%d.%m.%Y"):
            try:
                return datetime.strptime(s.strip()[:19], fmt)
            except ValueError:
                continue
        return None

    # Группируем по (restaurant_id, warehouse_id, writeoff_date)
    # чтобы разные инвентаризации одного склада создавали разные акты
    by_group: dict = defaultdict(list)
    skipped = []
    for item in body.items:
        _check_access(user, item.restaurant_id)

        wh = db.query(CoWarehouse).filter(
            CoWarehouse.id == item.warehouse_id,
            CoWarehouse.restaurant_id == item.restaurant_id,
        ).first()
        if not wh:
            skipped.append(f"warehouse_id={item.warehouse_id}: склад не найден")
            continue

        wo_dt = _parse_dt(item.writeoff_datetime)
        wo_date = wo_dt.date() if wo_dt else act_date_obj
        by_group[(item.restaurant_id, item.warehouse_id, wo_date, item.writeoff_datetime, item.inventory_datetime)].append(item)

    created_ids = []
    for (rid, wid, wo_date, wo_dt_str, inv_dt_str), items in by_group.items():
        inv_dt = _parse_dt(inv_dt_str)
        wo_dt = _parse_dt(wo_dt_str)
        group_sum = sum((it.resigned_sum or 0) for it in items if it.amount > 0)
        act = CoWriteoffAct(
            restaurant_id=rid,
            warehouse_id=wid,
            act_date=wo_date,
            inventory_datetime=inv_dt,
            writeoff_datetime=wo_dt,
            total_sum=group_sum if group_sum > 0 else None,
            comment=body.comment,
            status="draft",
            created_by=user.id,
        )
        db.add(act)
        db.flush()

        for it in items:
            if it.amount <= 0:
                continue
            db.add(CoWriteoffItem(
                act_id=act.id,
                product_id=it.product_id,
                amount=it.amount,
                resigned_sum=it.resigned_sum,
            ))

        created_ids.append(act.id)

    db.commit()
    return {"created_act_ids": created_ids, "skipped": skipped}


# ── List acts ─────────────────────────────────────────────────────────────────

@router.get("/")
def list_acts(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    allowed_ids = _user_restaurant_ids(user)
    q = db.query(CoWriteoffAct).order_by(CoWriteoffAct.act_date.desc(), CoWriteoffAct.id.desc())
    if allowed_ids is not None:
        q = q.filter(CoWriteoffAct.restaurant_id.in_(allowed_ids))

    acts = q.limit(200).all()

    rest_map = {r.id: r for r in db.query(CoRestaurant).all()}
    wh_map = {w.id: w for w in db.query(CoWarehouse).all()}

    return [
        {
            "id": a.id,
            "restaurant_id": a.restaurant_id,
            "restaurant_name": rest_map[a.restaurant_id].name if a.restaurant_id in rest_map else None,
            "warehouse_id": a.warehouse_id,
            "warehouse_name": wh_map[a.warehouse_id].name if a.warehouse_id in wh_map else None,
            "act_date": a.act_date.isoformat() if a.act_date else None,
            "inventory_datetime": _dt_iso(a.inventory_datetime),
            "writeoff_datetime": _dt_iso(a.writeoff_datetime),
            "total_sum": float(a.total_sum) if a.total_sum is not None else None,
            "comment": a.comment,
            "status": a.status,
            "iiko_doc_ids": a.iiko_doc_ids,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "posted_at": a.posted_at.isoformat() if a.posted_at else None,
            "items_count": len(a.items),
        }
        for a in acts
    ]


@router.get("/{act_id}")
def get_act(
    act_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    act = db.query(CoWriteoffAct).filter(CoWriteoffAct.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Акт не найден")
    _check_access(user, act.restaurant_id)

    rest = db.query(CoRestaurant).filter(CoRestaurant.id == act.restaurant_id).first()
    wh = db.query(CoWarehouse).filter(CoWarehouse.id == act.warehouse_id).first()

    items = []
    for it in act.items:
        product = it.product
        # Счёт из дефицитного склада нам неизвестен на этом этапе (акт уже создан),
        # поэтому просто показываем продукт и количество
        items.append({
            "id": it.id,
            "product_id": it.product_id,
            "product_name": product.name if product else None,
            "product_num": product.unit if product else None,
            "amount": float(it.amount),
        })

    return {
        "id": act.id,
        "restaurant_id": act.restaurant_id,
        "restaurant_name": rest.name if rest else None,
        "warehouse_id": act.warehouse_id,
        "warehouse_name": wh.name if wh else None,
        "act_date": act.act_date.isoformat() if act.act_date else None,
        "comment": act.comment,
        "status": act.status,
        "iiko_doc_ids": act.iiko_doc_ids,
        "created_at": act.created_at.isoformat() if act.created_at else None,
        "posted_at": act.posted_at.isoformat() if act.posted_at else None,
        "items": items,
    }


# ── Post to iiko ──────────────────────────────────────────────────────────────

@router.post("/{act_id}/post-to-iiko")
def post_act_to_iiko(
    act_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    from collections import defaultdict

    act = db.query(CoWriteoffAct).filter(CoWriteoffAct.id == act_id).first()
    if not act:
        raise HTTPException(status_code=404, detail="Акт не найден")
    _check_access(user, act.restaurant_id)

    restaurant = db.query(CoRestaurant).filter(CoRestaurant.id == act.restaurant_id).first()
    warehouse = db.query(CoWarehouse).filter(CoWarehouse.id == act.warehouse_id).first()
    if not warehouse or not warehouse.iiko_store_id:
        raise HTTPException(status_code=400, detail="Склад не привязан к iiko (нет iiko_store_id)")

    # Счёт берём из типа склада (склад списания)
    wh_type = warehouse.warehouse_type if warehouse.warehouse_type_id else None
    account = wh_type.account if wh_type else None

    if not account:
        raise HTTPException(
            status_code=400,
            detail=f"Склад '{warehouse.name}' не имеет типа с привязанным счётом. Настройте в Настройки → Типы складов."
        )

    items_list = []
    skipped = []
    for it in act.items:
        product = it.product
        if not product or not product.iiko_article_id:
            skipped.append(f"product_id={it.product_id}: нет iiko_article_id")
            continue
        items_list.append({
            "productId": product.iiko_article_id,
            "amount": float(it.amount),
        })

    if not items_list:
        raise HTTPException(status_code=400, detail=f"Нет позиций для отправки. {'; '.join(skipped[:5])}")

    if act.writeoff_datetime:
        # Точное время (инвентаризация − 2ч)
        date_str = act.writeoff_datetime.strftime("%Y-%m-%dT%H:%M:%S")
    elif act.inventory_datetime:
        # Дата известна, время нет — ставим 21:00 дня инвентаризации
        date_str = act.inventory_datetime.strftime("%Y-%m-%dT21:00:00")
    elif act.act_date:
        date_str = act.act_date.strftime("%Y-%m-%dT21:00:00")
    else:
        date_str = ""
    payload = {
        "dateIncoming": date_str,
        "status": "NEW",
        "comment": act.comment or f"Coffee Original {act.act_date}",
        "storeId": warehouse.iiko_store_id,
        "accountId": account.account_iiko_id,
        "items": items_list,
    }

    errors = []
    results = []
    try:
        resp = iiko_post_writeoff(restaurant, payload)
        results.append({"account": account.account_iiko_id, "items": len(items_list), "response": resp})
    except Exception as e:
        err_str = str(e)
        errors.append({"account": account.account_iiko_id, "error": err_str,
                       "period_closed": "is not in current period" in err_str})

    if results:
        act.status = "posted"
        act.iiko_doc_ids = [r.get("response", {}) if isinstance(r.get("response"), dict) else r for r in results]
        act.posted_at = datetime.now(timezone.utc)
        db.commit()

    return {
        "docs_sent": len(results),
        "errors": errors,
        "skipped": skipped,
        "results": results,
    }


# ── Clear history ─────────────────────────────────────────────────────────────

@router.delete("/history", status_code=204)
def clear_history(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """Удаляет все акты (и позиции) для ресторанов, доступных пользователю."""
    allowed_ids = _user_restaurant_ids(user)
    q = db.query(CoWriteoffAct)
    if allowed_ids is not None:
        q = q.filter(CoWriteoffAct.restaurant_id.in_(allowed_ids))
    acts = q.all()
    for act in acts:
        db.delete(act)
    db.commit()


# ── Settings: Preset ──────────────────────────────────────────────────────────

class PresetIn(BaseModel):
    preset_id: str


@_settings.get("/settings/preset")
def get_preset(db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    s = db.query(CoSetting).filter(CoSetting.key == PRESET_KEY).first()
    return {"preset_id": s.value if s else None}


@_settings.post("/settings/preset")
def save_preset(body: PresetIn, db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    pid = body.preset_id.strip()
    s = db.query(CoSetting).filter(CoSetting.key == PRESET_KEY).first()
    if s:
        s.value = pid
    else:
        db.add(CoSetting(key=PRESET_KEY, value=pid))
    db.commit()
    return {"preset_id": pid}


# ── Settings: iikoChain server ────────────────────────────────────────────────

@_settings.post("/settings/preset/activate")
def activate_preset(db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    s = db.query(CoSetting).filter(CoSetting.key == PRESET_KEY).first()
    if not s or not s.value:
        raise HTTPException(status_code=400, detail="Пресет не сохранён")

    chain_rest = (
        db.query(CoRestaurant).filter(CoRestaurant.code == "CO").first()
        or db.query(CoRestaurant).filter(CoRestaurant.is_active == True).first()
    )
    if not chain_rest:
        raise HTTPException(status_code=400, detail="Нет активных ресторанов")

    today = datetime.now().strftime("%Y-%m-%d")
    try:
        rows = fetch_olap(chain_rest, s.value, today, today)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"iiko ошибка: {e}")

    if not rows:
        from datetime import timedelta
        df90 = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        try:
            rows = fetch_olap(chain_rest, s.value, df90, today)
        except Exception:
            pass

    if not rows:
        return {"columns": [], "sample_rows": 0, "message": "Пресет доступен, но данных за последние 90 дней нет"}

    columns = list(rows[0].keys())
    return {"columns": columns, "sample_rows": len(rows)}


# ── Settings: Accounts sync from iiko ─────────────────────────────────────────

@_settings.post("/settings/sync-accounts")
def sync_accounts(db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    from app.services.co_iiko import _get_key

    rest = db.query(CoRestaurant).filter(CoRestaurant.is_active == True).first()
    if not rest:
        raise HTTPException(status_code=400, detail="Нет активных ресторанов")

    key = _get_key(rest.base_url, rest.iiko_login, rest.iiko_password_hash)
    r = requests.get(
        f"{rest.base_url}/resto/api/v2/entities/accounts/list",
        params={"key": key},
        timeout=60,
    )
    if not r.ok:
        raise HTTPException(status_code=502, detail=f"iiko вернул {r.status_code}: {r.text[:200]}")

    items = r.json()
    added = updated = 0
    for item in items:
        if item.get("deleted"):
            continue
        iiko_uuid = (item.get("id") or "").strip()
        name = (item.get("name") or "").strip()
        if not iiko_uuid or not name:
            continue
        existing = db.query(CoAccount).filter(CoAccount.account_iiko_id == iiko_uuid).first()
        if existing:
            existing.name = name
            updated += 1
        else:
            db.add(CoAccount(account_iiko_id=iiko_uuid, name=name))
            added += 1

    db.commit()
    total = db.query(CoAccount).count()
    return {"added": added, "updated": updated, "total": total}


@_settings.get("/settings/accounts")
def list_accounts(db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    return [
        {"id": a.id, "account_iiko_id": a.account_iiko_id, "name": a.name}
        for a in db.query(CoAccount).order_by(CoAccount.name).all()
    ]


@_settings.delete("/settings/accounts/{acc_id}", status_code=204)
def delete_account(acc_id: int, db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    a = db.query(CoAccount).filter(CoAccount.id == acc_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Не найден")
    db.delete(a)
    db.commit()


# ── Settings: Warehouse Types ─────────────────────────────────────────────────

class WarehouseTypeIn(BaseModel):
    name: str
    account_id: Optional[int] = None


class WarehouseTypeUpdate(BaseModel):
    name: Optional[str] = None
    account_id: Optional[int] = None


@_settings.get("/settings/warehouses")
def list_all_warehouses(db: Session = Depends(get_db), user: CoUser = Depends(get_current_co_user)):
    """Все склады (доступных пользователю ресторанов) с типами — для настройки типов."""
    allowed_ids = _user_restaurant_ids(user)
    q = db.query(CoWarehouse).join(
        CoRestaurant, CoWarehouse.restaurant_id == CoRestaurant.id
    ).filter(CoRestaurant.is_active == True, CoRestaurant.code != "CO")
    if allowed_ids is not None:
        q = q.filter(CoWarehouse.restaurant_id.in_(allowed_ids))
    whs = q.order_by(CoWarehouse.restaurant_id, CoWarehouse.name).all()
    rest_map = {r.id: r.name for r in db.query(CoRestaurant).all()}
    return [
        {
            "id": w.id,
            "name": w.name,
            "restaurant_id": w.restaurant_id,
            "restaurant_name": rest_map.get(w.restaurant_id),
            "is_writeoff_default": w.is_writeoff_default,
            "warehouse_type_id": w.warehouse_type_id,
            "warehouse_type_name": w.warehouse_type.name if w.warehouse_type else None,
        }
        for w in whs
    ]


class SetWarehouseTypeBody(BaseModel):
    warehouse_type_id: Optional[int] = None


@_settings.patch("/settings/warehouses/{wid}/type")
def set_warehouse_type(
    wid: int,
    body: SetWarehouseTypeBody,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """Назначить тип склада (доступно всем пользователям)."""
    w = db.query(CoWarehouse).filter(CoWarehouse.id == wid).first()
    if not w:
        raise HTTPException(status_code=404, detail="Склад не найден")
    _check_access(user, w.restaurant_id)
    w.warehouse_type_id = body.warehouse_type_id
    db.commit()
    wt = db.query(CoWarehouseType).filter(CoWarehouseType.id == w.warehouse_type_id).first() if w.warehouse_type_id else None
    return {"id": w.id, "warehouse_type_id": w.warehouse_type_id, "warehouse_type_name": wt.name if wt else None}


@_settings.get("/settings/products")
def list_products(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """Список всех товаров CO (для просмотра и синхронизации)."""
    products = db.query(CoProduct).filter(CoProduct.is_active == True).order_by(CoProduct.name).all()
    return {
        "total": len(products),
        "products": [
            {"id": p.id, "name": p.name, "unit": p.unit, "has_iiko_id": bool(p.iiko_article_id)}
            for p in products
        ],
    }


@_settings.post("/settings/sync-products")
def sync_products_all(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """Синхронизация товаров с центрального сервера CO — один запрос вместо 16."""
    chain = (
        db.query(CoRestaurant).filter(CoRestaurant.code == "CO").first()
        or db.query(CoRestaurant).filter(CoRestaurant.is_active == True).first()
    )
    if not chain:
        raise HTTPException(status_code=400, detail="Центральный сервер CO не найден")

    try:
        key = _get_key(chain.base_url, chain.iiko_login, chain.iiko_password_hash)
        resp = requests.get(
            f"{chain.base_url}/resto/api/v2/entities/products/list",
            params={"key": key, "includeDeleted": "false"},
            timeout=90,
        )
        resp.raise_for_status()
        items = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Ошибка соединения с iiko CO: {e}")

    existing = {p.iiko_article_id: p for p in db.query(CoProduct).all() if p.iiko_article_id}
    added = updated = 0

    for item in items:
        iiko_id = (item.get("id") or "").strip()
        name = (item.get("name") or "").strip()
        if not iiko_id or not name:
            continue
        if item.get("type") in ("DISH", "PREPARED", "SERVICE", "MODIFIER", "OUTER", "RATE"):
            continue

        if iiko_id in existing:
            existing[iiko_id].name = name
            updated += 1
        else:
            sp = db.begin_nested()
            try:
                p = CoProduct(iiko_article_id=iiko_id, name=name, unit=item.get("num", ""), is_active=True)
                db.add(p)
                db.flush()
                sp.commit()
                existing[iiko_id] = p
                added += 1
            except Exception:
                sp.rollback()
                p = db.query(CoProduct).filter(CoProduct.iiko_article_id == iiko_id).first()
                if p:
                    p.name = name
                    existing[iiko_id] = p
                    updated += 1

    db.commit()
    total = db.query(CoProduct).filter(CoProduct.is_active == True).count()
    return {"added": added, "updated": updated, "total": total, "errors": []}


@_settings.get("/settings/warehouse-types")
def list_warehouse_types(db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    types = db.query(CoWarehouseType).order_by(CoWarehouseType.name).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "account_id": t.account_id,
            "account_name": t.account.name if t.account else None,
            "account_iiko_id": t.account.account_iiko_id if t.account else None,
        }
        for t in types
    ]


@_settings.post("/settings/warehouse-types", status_code=201)
def create_warehouse_type(body: WarehouseTypeIn, db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    t = CoWarehouseType(name=body.name.strip(), account_id=body.account_id)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id, "name": t.name, "account_id": t.account_id}


@_settings.patch("/settings/warehouse-types/{type_id}")
def update_warehouse_type(
    type_id: int,
    body: WarehouseTypeUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_co_user),
):
    t = db.query(CoWarehouseType).filter(CoWarehouseType.id == type_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Тип склада не найден")
    if body.name is not None:
        t.name = body.name.strip()
    if body.account_id is not None:
        t.account_id = body.account_id
    elif body.account_id == 0:
        t.account_id = None
    db.commit()
    return {"id": t.id, "name": t.name, "account_id": t.account_id}


@_settings.delete("/settings/warehouse-types/{type_id}", status_code=204)
def delete_warehouse_type(type_id: int, db: Session = Depends(get_db), _=Depends(get_current_co_user)):
    t = db.query(CoWarehouseType).filter(CoWarehouseType.id == type_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Не найден")
    db.delete(t)
    db.commit()


# Register settings routes on the main router.
router.include_router(_settings, prefix="")
