"""Admin API for coffee_original — restaurants, warehouses, products, suppliers, users, iiko sync."""
import re
import xml.etree.ElementTree as ET
from typing import Optional, List

import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.models.co_models import (
    CoRestaurant, CoWarehouse, CoWarehouseType, CoUser, CoUserRestaurant, CoUserWarehouse,
    CoSupplier, CoProduct, CoProductMapping, CoProductContainer, CoInvoice, CoInvoiceItem,
)
from app.api.co_auth import require_co_admin, get_current_co_user, CoUser as _CoUser
from app.core.tenant_utils import (
    load_restaurant, load_warehouse, load_supplier,
    load_product, load_mapping, load_container,
)

router = APIRouter(prefix="/api/co/admin", tags=["co-admin"])


# ── iiko helpers ─────────────────────────────────────────────────────────────

def _normalize_url(url: str) -> str:
    url = url.strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def _iiko_session(restaurant: CoRestaurant) -> str:
    try:
        r = requests.get(
            f"{restaurant.base_url}/resto/api/auth",
            params={"login": restaurant.iiko_login, "pass": restaurant.iiko_password_hash},
            timeout=20,
        )
        if r.status_code == 401:
            raise HTTPException(status_code=400, detail="iiko: неверный логин или пароль (401). Проверьте SHA1 хэш пароля.")
        r.raise_for_status()
    except HTTPException:
        raise
    except requests.exceptions.MissingSchema:
        raise HTTPException(status_code=400, detail=f"Неверный URL: '{restaurant.base_url}'. Должен начинаться с https://")
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=502, detail=f"Не удалось подключиться к iiko: {restaurant.base_url}")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="iiko не отвечает (таймаут)")
    key = r.text.strip().strip('"')
    if not key or "error" in key.lower():
        raise HTTPException(status_code=502, detail=f"iiko auth error: {r.text}")
    return key


# ── Restaurants ──────────────────────────────────────────────────────────────

class RestaurantIn(BaseModel):
    code: str
    name: str
    base_url: str
    iiko_login: str
    iiko_password: str


class QuickRestaurantIn(BaseModel):
    code: str
    name: str
    base_url: str


class RestaurantUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    iiko_login: Optional[str] = None
    iiko_password: Optional[str] = None
    iiko_concept_id: Optional[str] = None
    inventory_preset_id: Optional[str] = None
    is_active: Optional[bool] = None


def _rest_dict(r: CoRestaurant) -> dict:
    return {
        "id": r.id, "code": r.code, "name": r.name,
        "base_url": r.base_url, "iiko_login": r.iiko_login,
        "iiko_concept_id": r.iiko_concept_id,
        "inventory_preset_id": r.inventory_preset_id,
        "is_active": r.is_active,
        "warehouses_count": len(r.warehouses),
    }


@router.get("/restaurants")
def list_restaurants(db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    if user.role == "admin":
        rows = db.query(CoRestaurant).filter(
            CoRestaurant.tenant_id == user.tenant_id
        ).order_by(CoRestaurant.name).all()
    else:
        allowed_ids = {r.id for r in user.restaurants}
        rows = db.query(CoRestaurant).filter(
            CoRestaurant.tenant_id == user.tenant_id,
            CoRestaurant.id.in_(allowed_ids),
        ).order_by(CoRestaurant.name).all()
    return [_rest_dict(r) for r in rows]


@router.post("/restaurants/quick", status_code=201)
def quick_create_restaurant(body: "QuickRestaurantIn", db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Create restaurant copying iiko credentials from first existing restaurant."""
    if db.query(CoRestaurant).filter(
        CoRestaurant.tenant_id == user.tenant_id,
        CoRestaurant.code == body.code.strip().upper(),
    ).first():
        raise HTTPException(status_code=400, detail="Ресторан с таким кодом уже существует")
    template = db.query(CoRestaurant).filter(
        CoRestaurant.tenant_id == user.tenant_id
    ).first()
    if not template:
        raise HTTPException(status_code=400, detail="Нет ресторанов для копирования настроек iiko")
    r = CoRestaurant(
        tenant_id=user.tenant_id,
        code=body.code.strip().upper(),
        name=body.name.strip(),
        base_url=_normalize_url(body.base_url),
        iiko_login=template.iiko_login,
        iiko_password_hash=template.iiko_password_hash,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _rest_dict(r)


@router.post("/restaurants", status_code=201)
def create_restaurant(body: RestaurantIn, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    if db.query(CoRestaurant).filter(
        CoRestaurant.tenant_id == user.tenant_id,
        CoRestaurant.code == body.code.strip(),
    ).first():
        raise HTTPException(status_code=400, detail="Ресторан с таким кодом уже существует")
    r = CoRestaurant(
        tenant_id=user.tenant_id,
        code=body.code.strip().upper(),
        name=body.name.strip(),
        base_url=_normalize_url(body.base_url),
        iiko_login=body.iiko_login.strip(),
        iiko_password_hash=body.iiko_password.strip(),
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _rest_dict(r)


@router.patch("/restaurants/{rid}")
def update_restaurant(rid: int, body: RestaurantUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    r = load_restaurant(db, rid, user)
    if body.name is not None:
        r.name = body.name.strip()
    if body.base_url is not None:
        r.base_url = _normalize_url(body.base_url)
    if body.iiko_login is not None:
        r.iiko_login = body.iiko_login.strip()
    if body.iiko_password is not None and body.iiko_password.strip():
        r.iiko_password_hash = body.iiko_password.strip()
    if body.iiko_concept_id is not None:
        r.iiko_concept_id = body.iiko_concept_id.strip() or None
    if body.inventory_preset_id is not None:
        r.inventory_preset_id = body.inventory_preset_id.strip() or None
    if body.is_active is not None:
        r.is_active = body.is_active
    db.commit()
    return _rest_dict(r)


@router.delete("/restaurants/{rid}", status_code=204)
def delete_restaurant(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    r = load_restaurant(db, rid, user)
    db.delete(r)
    db.commit()


# ── iiko sync: warehouses ────────────────────────────────────────────────────

@router.post("/restaurants/{rid}/sync/warehouses")
def sync_warehouses(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Pull stores from iiko → upsert into restaurant_warehouses."""
    r = load_restaurant(db, rid, user)

    key = _iiko_session(r)
    resp = requests.get(
        f"{r.base_url}/resto/api/corporation/stores",
        params={"key": key, "revisionFrom": -1},
        timeout=60,
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.text)

    # Собираем все концепции (type != STORE) — для справки
    concepts = []
    all_items = []
    for item in root.findall(".//corporateItemDto"):
        item_type = (item.findtext("type") or "").strip().upper()
        item_id = (item.findtext("id") or "").strip()
        item_name = (item.findtext("name") or "").strip()
        parent_id = (item.findtext("parentId") or "").strip()
        if item_type != "STORE":
            if item_id:
                concepts.append({"id": item_id, "name": item_name, "type": item_type})
            continue
        all_items.append({
            "iiko_store_id": item_id,
            "name": item_name,
            "parent_id": parent_id,
        })

    # Если задан iiko_concept_id — берём только склады этой концепции
    if r.iiko_concept_id:
        stores = [s for s in all_items if s["parent_id"] == r.iiko_concept_id]
    else:
        stores = all_items

    existing = {w.iiko_store_id: w for w in r.warehouses if w.iiko_store_id}
    added = updated = 0
    for s in stores:
        if not s["iiko_store_id"]:
            continue
        if s["iiko_store_id"] in existing:
            existing[s["iiko_store_id"]].name = s["name"]
            updated += 1
        else:
            db.add(CoWarehouse(restaurant_id=rid, name=s["name"], iiko_store_id=s["iiko_store_id"]))
            added += 1

    db.commit()
    return {
        "found": len(stores),
        "added": added,
        "updated": updated,
        "stores": stores,
        "concepts": concepts,
        "filtered_by_concept": r.iiko_concept_id or None,
    }


# ── iiko sync: products ──────────────────────────────────────────────────────

@router.post("/restaurants/{rid}/sync/products")
def sync_products(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Pull nomenclature from iiko → upsert into products."""
    r = load_restaurant(db, rid, user)

    key = _iiko_session(r)
    resp = requests.get(
        f"{r.base_url}/resto/api/v2/entities/products/list",
        params={"key": key, "includeDeleted": "false"},
        timeout=120,
    )
    resp.raise_for_status()
    items = resp.json()

    existing = {
        p.iiko_article_id: p
        for p in db.query(CoProduct).filter(CoProduct.tenant_id == user.tenant_id).all()
        if p.iiko_article_id
    }
    added = updated = containers_added = 0

    for item in items:
        iiko_id = (item.get("id") or "").strip()
        name = (item.get("name") or "").strip()
        if not iiko_id or not name:
            continue
        if item.get("type") in ("DISH", "PREPARED", "SERVICE", "MODIFIER", "OUTER", "RATE"):
            continue

        if iiko_id in existing:
            product = existing[iiko_id]
            product.name = name
            updated += 1
        else:
            sp = db.begin_nested()
            try:
                product = CoProduct(tenant_id=user.tenant_id, iiko_article_id=iiko_id, name=name, unit=item.get("num", ""))
                db.add(product)
                db.flush()
                sp.commit()
                existing[iiko_id] = product
                added += 1
            except Exception:
                # Concurrent sync already inserted this product — rollback savepoint only
                sp.rollback()
                product = db.query(CoProduct).filter(
                    CoProduct.iiko_article_id == iiko_id,
                    CoProduct.tenant_id == user.tenant_id,
                ).first()
                if not product:
                    continue
                product.name = name
                existing[iiko_id] = product
                updated += 1

        # Сохраняем контейнеры товара
        raw_containers = item.get("containers") or []
        if raw_containers:
            existing_containers = {
                c.iiko_container_id: c
                for c in db.query(CoProductContainer).filter(CoProductContainer.product_id == product.id).all()
            }
            for c in raw_containers:
                cid = (c.get("id") or "").strip()
                cname = (c.get("name") or "").strip()
                count = c.get("count") or 1
                if not cid or c.get("deleted"):
                    continue
                if cid in existing_containers:
                    existing_containers[cid].name = cname
                    existing_containers[cid].count = count
                else:
                    db.add(CoProductContainer(
                        product_id=product.id,
                        iiko_container_id=cid,
                        name=cname or "Упаковка",
                        count=count,
                    ))
                    containers_added += 1

    db.commit()
    return {"total_from_iiko": len(items), "added": added, "updated": updated, "containers_added": containers_added}


# ── iiko sync: suppliers ─────────────────────────────────────────────────────

@router.post("/restaurants/{rid}/sync/suppliers")
def sync_suppliers(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Pull suppliers from iiko → upsert into suppliers."""
    r = load_restaurant(db, rid, user)

    key = _iiko_session(r)
    resp = requests.get(
        f"{r.base_url}/resto/api/suppliers",
        params={"key": key},
        timeout=60,
    )
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    suppliers = []
    for item in root.findall(".//employee"):
        iiko_id = (item.findtext("id") or "").strip()
        name = (item.findtext("name") or "").strip()
        if item.findtext("deleted", "false").strip().lower() == "true":
            continue
        if not iiko_id or not name:
            continue
        raw_bin = (item.findtext("taxpayerIdNumber") or "").strip()
        # Нормализуем БИН — убираем пробелы (OCR и iiko могут добавлять их)
        clean_bin = re.sub(r"\s+", "", raw_bin) or None
        suppliers.append({
            "iiko_id": iiko_id,
            "name": name,
            "bin": clean_bin,
            "contact": (item.findtext("phone") or item.findtext("email") or "").strip() or None,
        })

    all_existing = db.query(CoSupplier).filter(CoSupplier.tenant_id == user.tenant_id).all()
    by_iiko_id = {s.iiko_id: s for s in all_existing if s.iiko_id}
    # Ручные поставщики (без iiko_id) — матчим по БИН или по имени
    by_bin  = {s.bin.strip(): s for s in all_existing if not s.iiko_id and s.bin}
    by_name = {s.name.strip().lower(): s for s in all_existing if not s.iiko_id}

    added = updated = linked = 0
    for s in suppliers:
        if s["iiko_id"] in by_iiko_id:
            sup = by_iiko_id[s["iiko_id"]]
            sup.name = s["name"]
            if s["bin"]:
                sup.bin = s["bin"]
            if s["contact"]:
                sup.contact = s["contact"]
            updated += 1
        else:
            # Попробуем привязать существующего ручного поставщика по БИН или имени
            manual = (
                by_bin.get(s["bin"].strip()) if s["bin"] else None
            ) or by_name.get(s["name"].strip().lower())
            if manual:
                manual.iiko_id = s["iiko_id"]
                manual.name = s["name"]
                if s["bin"]:
                    manual.bin = s["bin"]
                if s["contact"] and not manual.contact:
                    manual.contact = s["contact"]
                linked += 1
            else:
                db.add(CoSupplier(tenant_id=user.tenant_id, **s))
                added += 1

    db.commit()
    return {"found": len(suppliers), "added": added, "updated": updated, "linked": linked}


# ── Warehouses ───────────────────────────────────────────────────────────────

class WarehouseIn(BaseModel):
    name: str
    iiko_store_id: Optional[str] = None


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    iiko_store_id: Optional[str] = None
    is_active: Optional[bool] = None
    warehouse_type_id: Optional[int] = None


@router.get("/restaurants/{rid}/warehouses")
def list_warehouses(rid: int, active_only: bool = False, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    load_restaurant(db, rid, user)  # tenant-гейт
    if user.role != "admin":
        allowed_ids = {r.id for r in user.restaurants}
        if rid not in allowed_ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")
    q = db.query(CoWarehouse).filter(CoWarehouse.restaurant_id == rid)
    if active_only:
        q = q.filter(CoWarehouse.is_active == True)
    whs = q.order_by(CoWarehouse.name).all()
    return [
        {
            "id": w.id, "name": w.name, "iiko_store_id": w.iiko_store_id,
            "is_active": w.is_active, "is_writeoff_default": w.is_writeoff_default,
            "warehouse_type_id": w.warehouse_type_id,
            "warehouse_type_name": w.warehouse_type.name if w.warehouse_type else None,
        }
        for w in whs
    ]


@router.post("/restaurants/{rid}/warehouses", status_code=201)
def create_warehouse(rid: int, body: WarehouseIn, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    load_restaurant(db, rid, user)  # tenant-гейт
    w = CoWarehouse(restaurant_id=rid, name=body.name.strip(), iiko_store_id=body.iiko_store_id)
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"id": w.id, "name": w.name, "iiko_store_id": w.iiko_store_id, "is_active": w.is_active, "is_writeoff_default": w.is_writeoff_default}


@router.patch("/warehouses/{wid}")
def update_warehouse(wid: int, body: WarehouseUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    w = load_warehouse(db, wid, user)
    if body.name is not None:
        w.name = body.name.strip()
    if body.iiko_store_id is not None:
        w.iiko_store_id = body.iiko_store_id.strip() or None
    if body.is_active is not None:
        w.is_active = body.is_active
    if body.warehouse_type_id is not None:
        w.warehouse_type_id = body.warehouse_type_id if body.warehouse_type_id > 0 else None
    db.commit()
    return {
        "id": w.id, "name": w.name, "iiko_store_id": w.iiko_store_id,
        "is_active": w.is_active, "is_writeoff_default": w.is_writeoff_default,
        "warehouse_type_id": w.warehouse_type_id,
        "warehouse_type_name": w.warehouse_type.name if w.warehouse_type else None,
    }


@router.post("/warehouses/{wid}/set-writeoff-default", status_code=200)
def set_writeoff_default(wid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Помечает склад как склад для списания (один на ресторан). Снимает флаг с остальных складов того же ресторана."""
    w = load_warehouse(db, wid, user)
    # снимаем флаг у других складов этого ресторана
    db.query(CoWarehouse).filter(
        CoWarehouse.restaurant_id == w.restaurant_id,
        CoWarehouse.id != wid,
    ).update({"is_writeoff_default": False})
    w.is_writeoff_default = True
    db.commit()
    return {"ok": True, "warehouse_id": wid}


@router.get("/restaurants/{rid}/iiko/warehouses")
def fetch_iiko_warehouses(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Return warehouses from iiko without saving — marks which are already added."""
    r = load_restaurant(db, rid, user)
    key = _iiko_session(r)
    resp = requests.get(
        f"{r.base_url}/resto/api/corporation/stores",
        params={"key": key, "revisionFrom": -1},
        timeout=60,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.text)
    stores = []
    for item in root.findall(".//corporateItemDto"):
        if (item.findtext("type") or "").strip().upper() != "STORE":
            continue
        iiko_id = (item.findtext("id") or "").strip()
        name = (item.findtext("name") or "").strip()
        parent_id = (item.findtext("parentId") or "").strip()
        if not iiko_id:
            continue
        stores.append({"iiko_store_id": iiko_id, "name": name, "parent_id": parent_id})
    if r.iiko_concept_id:
        stores = [s for s in stores if s["parent_id"] == r.iiko_concept_id]
    existing_ids = {w.iiko_store_id for w in r.warehouses if w.iiko_store_id}
    for s in stores:
        s["added"] = s["iiko_store_id"] in existing_ids
    return sorted(stores, key=lambda s: s["name"])


@router.delete("/restaurants/{rid}/warehouses")
def clear_warehouses(rid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    """Delete all warehouses for a restaurant that have no invoices attached."""
    load_restaurant(db, rid, user)  # tenant-гейт
    used_ids = {row[0] for row in db.query(CoInvoice.warehouse_id).filter(CoInvoice.restaurant_id == rid).all()}
    q = db.query(CoWarehouse).filter(CoWarehouse.restaurant_id == rid)
    if used_ids:
        q = q.filter(~CoWarehouse.id.in_(used_ids))
    count = q.count()
    q.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count, "skipped": len(used_ids)}


@router.delete("/warehouses/{wid}", status_code=204)
def delete_warehouse(wid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    w = load_warehouse(db, wid, user)
    db.delete(w)
    db.commit()


# ── Suppliers ────────────────────────────────────────────────────────────────

class SupplierIn(BaseModel):
    name: str
    bin: Optional[str] = None
    contact: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    bin: Optional[str] = None
    contact: Optional[str] = None
    is_active: Optional[bool] = None


def _sup_dict(s: CoSupplier) -> dict:
    return {"id": s.id, "iiko_id": s.iiko_id, "name": s.name, "bin": s.bin, "contact": s.contact, "is_active": s.is_active}


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    return [_sup_dict(s) for s in db.query(CoSupplier).filter(
        CoSupplier.tenant_id == user.tenant_id
    ).order_by(CoSupplier.name).all()]


@router.post("/suppliers", status_code=201)
def create_supplier(body: SupplierIn, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    s = CoSupplier(name=body.name.strip(), bin=body.bin, contact=body.contact, tenant_id=user.tenant_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    return _sup_dict(s)


@router.patch("/suppliers/{sid}")
def update_supplier(sid: int, body: SupplierUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    s = load_supplier(db, sid, user)
    if body.name is not None:
        s.name = body.name.strip()
    if body.bin is not None:
        s.bin = body.bin.strip() or None
    if body.contact is not None:
        s.contact = body.contact.strip() or None
    if body.is_active is not None:
        s.is_active = body.is_active
    db.commit()
    return _sup_dict(s)


@router.delete("/suppliers/{sid}", status_code=204)
def delete_supplier(sid: int, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    s = load_supplier(db, sid, user)
    db.delete(s)
    db.commit()


# ── Products ─────────────────────────────────────────────────────────────────

@router.get("/products")
def list_products(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    user: _CoUser = Depends(get_current_co_user),
):
    q = db.query(CoProduct).filter(CoProduct.tenant_id == user.tenant_id)
    if search:
        q = q.filter(CoProduct.name.ilike(f"%{search}%"))
    products = q.order_by(CoProduct.name).limit(2000).all()
    return [{"id": p.id, "iiko_article_id": p.iiko_article_id, "name": p.name, "unit": p.unit, "is_active": p.is_active} for p in products]


@router.patch("/products/{pid}")
def update_product(pid: int, body: dict, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    p = load_product(db, pid, user)
    if "name" in body and body["name"]:
        p.name = body["name"].strip()
    if "unit" in body:
        p.unit = body["unit"]
    if "is_active" in body:
        p.is_active = body["is_active"]
    db.commit()
    return {"id": p.id, "iiko_article_id": p.iiko_article_id, "name": p.name, "unit": p.unit, "is_active": p.is_active}


# ── Users ────────────────────────────────────────────────────────────────────

class UserIn(BaseModel):
    email: str
    name: str
    password: str
    role: str = "user"
    restaurant_ids: List[int] = []


class UserUpdate(BaseModel):
    name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    restaurant_ids: Optional[List[int]] = None


def _user_dict(u: CoUser) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name,
        "role": u.role, "is_active": u.is_active,
        "restaurant_ids": [r.id for r in u.restaurants],
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    return [_user_dict(u) for u in db.query(CoUser).filter(
        CoUser.tenant_id == user.tenant_id
    ).order_by(CoUser.name).all()]


@router.post("/users", status_code=201)
def create_user(body: UserIn, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="role: admin | user")
    if db.query(CoUser).filter(
        CoUser.tenant_id == user.tenant_id,
        CoUser.email == body.email.strip().lower(),
    ).first():
        raise HTTPException(status_code=400, detail="Email уже занят")
    u = CoUser(
        tenant_id=user.tenant_id,
        email=body.email.strip().lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    if body.restaurant_ids:
        u.restaurants = db.query(CoRestaurant).filter(
            CoRestaurant.tenant_id == user.tenant_id,
            CoRestaurant.id.in_(body.restaurant_ids),
        ).all()
    db.add(u)
    db.commit()
    db.refresh(u)
    return _user_dict(u)


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    u = db.query(CoUser).filter(
        CoUser.id == uid,
        CoUser.tenant_id == user.tenant_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if body.name is not None:
        u.name = body.name.strip()
    if body.password:
        u.password_hash = hash_password(body.password)
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="role: admin | user")
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.restaurant_ids is not None:
        u.restaurants = db.query(CoRestaurant).filter(
            CoRestaurant.tenant_id == user.tenant_id,
            CoRestaurant.id.in_(body.restaurant_ids),
        ).all()
    db.commit()
    return _user_dict(u)


@router.delete("/users/{uid}", status_code=204)
def delete_user(uid: int, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    u = db.query(CoUser).filter(
        CoUser.id == uid,
        CoUser.tenant_id == user.tenant_id,
    ).first()
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.delete(u)
    db.commit()


# ── Product Mapping ───────────────────────────────────────────────────────────

class MappingIn(BaseModel):
    supplier_id: int
    product_id: Optional[int] = None
    supplier_product_name: str
    supplier_product_code: Optional[str] = None
    container_id: Optional[int] = None


class MappingUpdate(BaseModel):
    supplier_id: Optional[int] = None
    product_id: Optional[int] = None
    supplier_product_name: Optional[str] = None
    supplier_product_code: Optional[str] = None
    container_id: Optional[int] = None


def _mapping_dict(m: CoProductMapping, db: Session, user: _CoUser) -> dict:
    product = db.query(CoProduct).filter(
        CoProduct.id == m.product_id, CoProduct.tenant_id == user.tenant_id
    ).first() if m.product_id else None
    supplier = db.query(CoSupplier).filter(
        CoSupplier.id == m.supplier_id, CoSupplier.tenant_id == user.tenant_id
    ).first()
    container = db.query(CoProductContainer).join(
        CoProduct, CoProductContainer.product_id == CoProduct.id
    ).filter(
        CoProductContainer.id == m.container_id, CoProduct.tenant_id == user.tenant_id
    ).first() if m.container_id else None
    return {
        "id": m.id,
        "supplier_id": m.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "supplier_product_name": m.supplier_product_name,
        "supplier_product_code": m.supplier_product_code,
        "product_id": m.product_id,
        "product_name": product.name if product else None,
        "product_iiko_id": product.iiko_article_id if product else None,
        "container_id": m.container_id,
        "container_name": container.name if container else None,
        "container_count": float(container.count) if container else None,
        "container_iiko_id": container.iiko_container_id if container else None,
    }


@router.get("/mappings")
def list_mappings(
    supplier_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: _CoUser = Depends(get_current_co_user),
):
    q = db.query(CoProductMapping).join(
        CoSupplier, CoProductMapping.supplier_id == CoSupplier.id
    ).filter(CoSupplier.tenant_id == user.tenant_id)
    if supplier_id:
        q = q.filter(CoProductMapping.supplier_id == supplier_id)
    return [_mapping_dict(m, db, user) for m in q.order_by(CoProductMapping.supplier_product_name).all()]


@router.post("/mappings", status_code=201)
def create_mapping(body: MappingIn, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    load_supplier(db, body.supplier_id, user)
    if body.product_id:
        load_product(db, body.product_id, user)
    m = CoProductMapping(
        supplier_id=body.supplier_id,
        product_id=body.product_id,
        supplier_product_name=body.supplier_product_name.strip(),
        supplier_product_code=body.supplier_product_code.strip() if body.supplier_product_code else None,
        container_id=body.container_id,
    )
    db.add(m)
    db.flush()

    # Обновляем все несопоставленные позиции накладных этого поставщика
    if body.product_id:
        invoices = db.query(CoInvoice).filter(CoInvoice.supplier_id == body.supplier_id).all()
        invoice_ids = [inv.id for inv in invoices]
        if invoice_ids:
            updated = (db.query(CoInvoiceItem)
               .filter(
                   CoInvoiceItem.invoice_id.in_(invoice_ids),
                   CoInvoiceItem.product_id.is_(None),
                   CoInvoiceItem.supplier_product_name == body.supplier_product_name.strip(),
               )
               .update({"product_id": body.product_id}, synchronize_session=False))

            # Помечаем отправленные накладные как требующие повторной отправки
            if updated:
                affected_item_invoice_ids = [
                    row.invoice_id for row in
                    db.query(CoInvoiceItem.invoice_id)
                    .filter(
                        CoInvoiceItem.invoice_id.in_(invoice_ids),
                        CoInvoiceItem.supplier_product_name == body.supplier_product_name.strip(),
                    ).all()
                ]
                (db.query(CoInvoice)
                   .filter(
                       CoInvoice.id.in_(affected_item_invoice_ids),
                       CoInvoice.status == "sent",
                   )
                   .update({"needs_resend": True}, synchronize_session=False))

    db.commit()
    db.refresh(m)
    return _mapping_dict(m, db, user)


@router.patch("/mappings/{mid}")
def update_mapping(mid: int, body: MappingUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    m = load_mapping(db, mid, user)
    if body.supplier_id is not None:
        load_supplier(db, body.supplier_id, user)
        m.supplier_id = body.supplier_id
    if body.supplier_product_name is not None:
        m.supplier_product_name = body.supplier_product_name.strip()
    if body.supplier_product_code is not None:
        m.supplier_product_code = body.supplier_product_code.strip() or None
    if "container_id" in body.model_fields_set:
        m.container_id = body.container_id
    if "product_id" in body.model_fields_set:
        if body.product_id:
            load_product(db, body.product_id, user)
        m.product_id = body.product_id
    db.commit()
    return _mapping_dict(m, db, user)


@router.delete("/mappings/{mid}", status_code=204)
def delete_mapping(mid: int, db: Session = Depends(get_db), user: _CoUser = Depends(get_current_co_user)):
    m = load_mapping(db, mid, user)
    db.delete(m)
    db.commit()


# ── Product Containers ────────────────────────────────────────────────────────

class ContainerIn(BaseModel):
    product_id: int
    iiko_container_id: str
    name: str
    count: float


class ContainerUpdate(BaseModel):
    iiko_container_id: Optional[str] = None
    name: Optional[str] = None
    count: Optional[float] = None


def _container_dict(c: CoProductContainer) -> dict:
    return {
        "id": c.id,
        "product_id": c.product_id,
        "product_name": c.product.name if c.product else None,
        "iiko_container_id": c.iiko_container_id,
        "name": c.name,
        "count": float(c.count),
    }


@router.get("/containers")
def list_containers(
    product_id: Optional[int] = None,
    db: Session = Depends(get_db),
    user: _CoUser = Depends(get_current_co_user),
):
    q = db.query(CoProductContainer).join(
        CoProduct, CoProductContainer.product_id == CoProduct.id
    ).filter(CoProduct.tenant_id == user.tenant_id)
    if product_id:
        q = q.filter(CoProductContainer.product_id == product_id)
    return [_container_dict(c) for c in q.order_by(CoProductContainer.product_id).all()]


@router.post("/containers", status_code=201)
def create_container(body: ContainerIn, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    load_product(db, body.product_id, user)
    c = CoProductContainer(
        product_id=body.product_id,
        iiko_container_id=body.iiko_container_id.strip(),
        name=body.name.strip(),
        count=body.count,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _container_dict(c)


@router.patch("/containers/{cid}")
def update_container(cid: int, body: ContainerUpdate, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    c = load_container(db, cid, user)
    if body.iiko_container_id is not None:
        c.iiko_container_id = body.iiko_container_id.strip()
    if body.name is not None:
        c.name = body.name.strip()
    if body.count is not None:
        c.count = body.count
    db.commit()
    return _container_dict(c)


@router.delete("/containers/{cid}", status_code=204)
def delete_container(cid: int, db: Session = Depends(get_db), user: _CoUser = Depends(require_co_admin)):
    c = load_container(db, cid, user)
    db.delete(c)
    db.commit()
