"""
Admin API — только для role=admin или role=co.
Управление пользователями, ресторанами, нормами, пресетами, справочниками.
"""
import io
import xml.etree.ElementTree as ET

import requests
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.database import get_db
from app.core.security import require_co, hash_password
from app.models.catalog import AblProduct, ProductCatalog, ProductGroup, WasteRate, Supplier
from app.models.restaurant import PresetDefinition, Restaurant, restaurant_presets
from app.models.user import User
from app.services.iiko import get_session_key

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ════════════════════════════════════════════════════════════════
# ПОЛЬЗОВАТЕЛИ
# ════════════════════════════════════════════════════════════════

class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "store"          # admin | co | store
    restaurant_ids: List[int] = []


class UpdateUserRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    restaurant_ids: Optional[List[int]] = None


def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "role": u.role,
        "is_active": u.is_active,
        "restaurant_ids": [r.id for r in u.restaurants],
        "restaurants": [{"id": r.id, "code": r.code, "name": r.name} for r in u.restaurants],
    }


@router.get("/users")
def list_users(db: Session = Depends(get_db), _=Depends(require_co)):
    return [_user_dict(u) for u in db.query(User).order_by(User.username).all()]


@router.get("/users/{user_id}")
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _user_dict(u)


@router.post("/users", status_code=201)
def create_user(body: CreateUserRequest, db: Session = Depends(get_db), _=Depends(require_co)):
    if body.role not in ("admin", "co", "store"):
        raise HTTPException(status_code=400, detail="role должна быть: admin, co, store")
    if db.query(User).filter(User.username == body.username.strip().lower()).first():
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    user = User(
        username=body.username.strip().lower(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    if body.restaurant_ids:
        user.restaurants = db.query(Restaurant).filter(Restaurant.id.in_(body.restaurant_ids)).all()

    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_dict(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if body.password:
        user.password_hash = hash_password(body.password)
    if body.role is not None:
        if body.role not in ("admin", "co", "store"):
            raise HTTPException(status_code=400, detail="role должна быть: admin, co, store")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.restaurant_ids is not None:
        user.restaurants = db.query(Restaurant).filter(Restaurant.id.in_(body.restaurant_ids)).all()

    db.commit()
    return _user_dict(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    db.delete(user)
    db.commit()


# ════════════════════════════════════════════════════════════════
# РЕСТОРАНЫ
# ════════════════════════════════════════════════════════════════

class PresetInput(BaseModel):
    type: str
    uuid: str


class CreateRestaurantRequest(BaseModel):
    code: str
    name: str
    department_name: str = ""
    base_url: str
    iiko_login: str
    iiko_password: str
    store_id: Optional[str] = None
    presets: List[PresetInput] = []


class UpdateRestaurantRequest(BaseModel):
    name: Optional[str] = None
    department_name: Optional[str] = None
    base_url: Optional[str] = None
    iiko_login: Optional[str] = None
    iiko_password: Optional[str] = None
    store_id: Optional[str] = None
    is_active: Optional[bool] = None
    google_sheet_url: Optional[str] = None
    checklist_start_hour: Optional[int] = None
    presets: Optional[List[PresetInput]] = None


def _upsert_presets(restaurant: Restaurant, preset_inputs: list, db: Session):
    """Обновляет OLAP-пресеты ресторана. Создаёт PresetDefinition если нет."""
    restaurant.presets = []
    db.flush()
    for p in preset_inputs:
        if not p.uuid.strip():
            continue
        existing = db.query(PresetDefinition).filter(
            PresetDefinition.preset_type == p.type,
            PresetDefinition.preset_uuid == p.uuid.strip(),
        ).first()
        if not existing:
            existing = PresetDefinition(preset_type=p.type, preset_uuid=p.uuid.strip())
            db.add(existing)
            db.flush()
        if existing not in restaurant.presets:
            restaurant.presets.append(existing)


def _restaurant_dict(r: Restaurant) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "name": r.name,
        "department_name": r.department_name,
        "base_url": r.base_url,
        "iiko_login": r.iiko_login,
        "store_id": r.store_id,
        "is_active": r.is_active,
        "feat_invoices":  r.feat_invoices  if r.feat_invoices  is not None else True,
        "feat_analytics": r.feat_analytics if r.feat_analytics is not None else True,
        "feat_reports":   r.feat_reports   if r.feat_reports   is not None else True,
        "feat_planning":  r.feat_planning  if r.feat_planning  is not None else True,
        "feat_checklist": r.feat_checklist if r.feat_checklist is not None else True,
        "google_sheet_url": r.google_sheet_url,
        "checklist_start_hour": r.checklist_start_hour if r.checklist_start_hour is not None else 7,
        "presets": [
            {"type": p.preset_type, "uuid": p.preset_uuid}
            for p in r.presets
        ],
    }


@router.get("/restaurants")
def list_restaurants(db: Session = Depends(get_db), _=Depends(require_co)):
    return [
        _restaurant_dict(r)
        for r in db.query(Restaurant).order_by(Restaurant.code).all()
    ]


@router.get("/restaurants/{restaurant_id}")
def get_restaurant(restaurant_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    return _restaurant_dict(r)


@router.post("/restaurants", status_code=201)
def create_restaurant(
    body: CreateRestaurantRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    if db.query(Restaurant).filter(Restaurant.code == body.code.strip()).first():
        raise HTTPException(status_code=400, detail="Ресторан с таким кодом уже существует")

    restaurant = Restaurant(
        code=body.code.strip(),
        name=body.name.strip(),
        department_name=body.department_name.strip() or body.name.strip(),
        base_url=body.base_url.strip(),
        iiko_login=body.iiko_login.strip(),
        iiko_password_hash=body.iiko_password,
        store_id=body.store_id,
        is_active=True,
    )
    db.add(restaurant)
    db.flush()

    if body.presets:
        _upsert_presets(restaurant, body.presets, db)

    db.commit()
    db.refresh(restaurant)
    return _restaurant_dict(restaurant)


@router.patch("/restaurants/{restaurant_id}")
def update_restaurant(
    restaurant_id: int,
    body: UpdateRestaurantRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if body.name is not None:
        restaurant.name = body.name.strip()
    if body.department_name is not None:
        restaurant.department_name = body.department_name.strip()
    if body.base_url is not None:
        restaurant.base_url = body.base_url.strip()
    if body.iiko_login is not None:
        restaurant.iiko_login = body.iiko_login.strip()
    if body.iiko_password is not None and body.iiko_password.strip():
        restaurant.iiko_password_hash = body.iiko_password.strip()
    if body.store_id is not None:
        restaurant.store_id = body.store_id.strip() or None
    if body.is_active is not None:
        restaurant.is_active = body.is_active
    if body.presets is not None:
        _upsert_presets(restaurant, body.presets, db)
    if body.google_sheet_url is not None:
        restaurant.google_sheet_url = body.google_sheet_url.strip() or None
    if body.checklist_start_hour is not None:
        restaurant.checklist_start_hour = max(0, min(23, body.checklist_start_hour))

    db.commit()
    return _restaurant_dict(restaurant)


class UpdateFeaturesRequest(BaseModel):
    feat_invoices:  Optional[bool] = None
    feat_analytics: Optional[bool] = None
    feat_reports:   Optional[bool] = None
    feat_planning:  Optional[bool] = None
    feat_checklist: Optional[bool] = None


@router.patch("/restaurants/{restaurant_id}/features")
def update_restaurant_features(
    restaurant_id: int,
    body: UpdateFeaturesRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Управление доступом к функциям для ресторана (только ЦО)."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    if body.feat_invoices  is not None: restaurant.feat_invoices  = body.feat_invoices
    if body.feat_analytics is not None: restaurant.feat_analytics = body.feat_analytics
    if body.feat_reports   is not None: restaurant.feat_reports   = body.feat_reports
    if body.feat_planning  is not None: restaurant.feat_planning  = body.feat_planning
    if body.feat_checklist is not None: restaurant.feat_checklist = body.feat_checklist
    db.commit()
    return {
        "id":            restaurant.id,
        "name":          restaurant.name,
        "feat_invoices":  restaurant.feat_invoices,
        "feat_analytics": restaurant.feat_analytics,
        "feat_reports":   restaurant.feat_reports,
        "feat_planning":  restaurant.feat_planning,
        "feat_checklist": restaurant.feat_checklist,
    }


@router.delete("/restaurants/{restaurant_id}", status_code=204)
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    # RESTRICT на reports/invoices — если они есть, PostgreSQL сам выдаст ошибку
    try:
        db.delete(restaurant)
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Нельзя удалить ресторан: есть связанные отчёты или накладные",
        )


# ════════════════════════════════════════════════════════════════
# НОРМЫ СПИСАНИЯ (waste_rates)
# ════════════════════════════════════════════════════════════════

class WasteRateItem(BaseModel):
    group_id: int
    rate_pct: float


@router.get("/restaurants/{restaurant_id}/waste-rates")
def get_waste_rates(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    rates = (
        db.query(WasteRate, ProductGroup)
        .join(ProductGroup, WasteRate.group_id == ProductGroup.id)
        .filter(WasteRate.restaurant_id == restaurant_id)
        .order_by(ProductGroup.name)
        .all()
    )
    return [
        {"group_id": wr.group_id, "group_name": g.name, "rate_pct": wr.rate_pct}
        for wr, g in rates
    ]


@router.put("/restaurants/{restaurant_id}/waste-rates")
def update_waste_rates(
    restaurant_id: int,
    rates: List[WasteRateItem],
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Полная замена норм для ресторана — передаём весь список."""
    if not db.query(Restaurant).filter(Restaurant.id == restaurant_id).first():
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    for item in rates:
        existing = db.query(WasteRate).filter(
            WasteRate.restaurant_id == restaurant_id,
            WasteRate.group_id == item.group_id,
        ).first()
        if existing:
            existing.rate_pct = item.rate_pct
        else:
            db.add(WasteRate(
                restaurant_id=restaurant_id,
                group_id=item.group_id,
                rate_pct=item.rate_pct,
            ))

    db.commit()
    return {"updated": len(rates)}


# ════════════════════════════════════════════════════════════════
# ГРУППЫ ТОВАРОВ
# ════════════════════════════════════════════════════════════════

@router.get("/product-groups")
def list_product_groups(db: Session = Depends(get_db), _=Depends(require_co)):
    return [
        {"id": g.id, "name": g.name, "account_id": g.account_id}
        for g in db.query(ProductGroup).order_by(ProductGroup.name).all()
    ]


class CreateGroupRequest(BaseModel):
    name: str
    account_id: Optional[int] = None


class UpdateGroupRequest(BaseModel):
    name: Optional[str] = None
    account_id: Optional[int] = None


@router.post("/product-groups", status_code=201)
def create_product_group(body: CreateGroupRequest, db: Session = Depends(get_db), _=Depends(require_co)):
    if db.query(ProductGroup).filter(ProductGroup.name == body.name.strip()).first():
        raise HTTPException(status_code=400, detail="Группа с таким названием уже существует")
    g = ProductGroup(name=body.name.strip(), account_id=body.account_id)
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"id": g.id, "name": g.name, "account_id": g.account_id}


@router.patch("/product-groups/{group_id}")
def update_product_group(
    group_id: int,
    body: UpdateGroupRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    g = db.query(ProductGroup).filter(ProductGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    if body.name is not None:
        g.name = body.name.strip()
    if "account_id" in body.model_fields_set:
        g.account_id = body.account_id
    db.commit()
    return {"id": g.id, "name": g.name, "account_id": g.account_id}


@router.delete("/product-groups/{group_id}", status_code=204)
def delete_product_group(group_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    g = db.query(ProductGroup).filter(ProductGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    has_products = db.query(ProductCatalog).filter(ProductCatalog.group_id == group_id).count()
    if has_products:
        raise HTTPException(status_code=409, detail=f"Нельзя удалить: в группе {has_products} товаров. Сначала переназначьте их.")
    db.query(WasteRate).filter(WasteRate.group_id == group_id).delete()
    db.delete(g)
    db.commit()


# ════════════════════════════════════════════════════════════════
# СЧЕТА СПИСАНИЯ (accounts)
# ════════════════════════════════════════════════════════════════

from app.models.catalog import Account


class CreateAccountRequest(BaseModel):
    account_iiko_id: str
    name: str


class UpdateAccountRequest(BaseModel):
    account_iiko_id: Optional[str] = None
    name: Optional[str] = None


@router.get("/accounts")
def list_accounts(db: Session = Depends(get_db), _=Depends(require_co)):
    accounts = db.query(Account).order_by(Account.name).all()
    groups = db.query(ProductGroup).all()
    groups_by_account = {}
    for g in groups:
        if g.account_id:
            groups_by_account.setdefault(g.account_id, []).append({"id": g.id, "name": g.name})
    return [
        {
            "id": a.id,
            "account_iiko_id": a.account_iiko_id,
            "name": a.name,
            "groups": groups_by_account.get(a.id, []),
        }
        for a in accounts
    ]


@router.post("/accounts", status_code=201)
def create_account(body: CreateAccountRequest, db: Session = Depends(get_db), _=Depends(require_co)):
    if db.query(Account).filter(Account.account_iiko_id == body.account_iiko_id.strip()).first():
        raise HTTPException(status_code=400, detail="Счёт с таким IIKO ID уже существует")
    a = Account(account_iiko_id=body.account_iiko_id.strip(), name=body.name.strip())
    db.add(a)
    db.commit()
    db.refresh(a)
    return {"id": a.id, "account_iiko_id": a.account_iiko_id, "name": a.name, "groups": []}


@router.patch("/accounts/{account_id}")
def update_account(
    account_id: int,
    body: UpdateAccountRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    if body.account_iiko_id is not None:
        a.account_iiko_id = body.account_iiko_id.strip()
    if body.name is not None:
        a.name = body.name.strip()
    db.commit()
    return {"id": a.id, "account_iiko_id": a.account_iiko_id, "name": a.name}


@router.delete("/accounts/{account_id}", status_code=204)
def delete_account(account_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    a = db.query(Account).filter(Account.id == account_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    # Отвязываем группы
    db.query(ProductGroup).filter(ProductGroup.account_id == account_id).update({"account_id": None})
    db.delete(a)
    db.commit()


# ════════════════════════════════════════════════════════════════
# ТЕСТ ПОДКЛЮЧЕНИЯ IIKO
# ════════════════════════════════════════════════════════════════

@router.post("/iiko/test-connection/{restaurant_id}")
def test_iiko_connection(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    try:
        key = get_session_key(db, restaurant)
        return {"ok": True, "session_key": key[:8] + "..."}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ════════════════════════════════════════════════════════════════
# СПРАВОЧНИК ТОВАРОВ (product_catalog)
# ════════════════════════════════════════════════════════════════

@router.get("/product-catalog")
def list_product_catalog(
    filter: str = "all",   # all | no_group | deleted | no_iiko_id
    search: str = "",
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    query = db.query(ProductCatalog, ProductGroup).outerjoin(
        ProductGroup, ProductCatalog.group_id == ProductGroup.id
    )
    if filter == "no_group":
        query = query.filter(ProductCatalog.group_id == None)
    elif filter == "deleted":
        query = query.filter(ProductCatalog.is_deleted == True)
    elif filter == "no_iiko_id":
        query = query.filter(
            (ProductCatalog.product_iiko_id == None) | (ProductCatalog.product_iiko_id == "")
        )
    if search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            ProductCatalog.name.ilike(s) | ProductCatalog.product_num.ilike(s)
        )

    total = query.count()
    rows = query.order_by(ProductCatalog.product_num).offset(offset).limit(limit).all()

    total_all   = db.query(ProductCatalog).count()
    no_group    = db.query(ProductCatalog).filter(ProductCatalog.group_id == None).count()
    deleted_cnt = db.query(ProductCatalog).filter(ProductCatalog.is_deleted == True).count()

    return {
        "total": total,
        "stats": {"total_all": total_all, "no_group": no_group, "deleted": deleted_cnt},
        "items": [
            {
                "id": p.id,
                "product_num": p.product_num,
                "name": p.name,
                "group": g.name if g else None,
                "group_id": p.group_id,
                "unit_type": p.unit_type,
                "product_iiko_id": p.product_iiko_id,
                "is_deleted": p.is_deleted,
            }
            for p, g in rows
        ],
    }


# ════════════════════════════════════════════════════════════════
# ABL СТАТИСТИКА
# ════════════════════════════════════════════════════════════════

@router.get("/abl-stats")
def abl_stats(db: Session = Depends(get_db), _=Depends(require_co)):
    total   = db.query(AblProduct).count()
    linked  = db.query(AblProduct).filter(AblProduct.product_catalog_id.isnot(None)).count()
    return {"total": total, "linked": linked, "not_linked": total - linked}


# ════════════════════════════════════════════════════════════════
# IIKO SYNC
# ════════════════════════════════════════════════════════════════

@router.post("/iiko/sync-suppliers/{restaurant_id}")
def sync_suppliers(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Загружает поставщиков из IIKO → таблица suppliers."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    key = get_session_key(db, restaurant)
    r = requests.get(f"{restaurant.base_url}/resto/api/suppliers",
                     params={"key": key}, timeout=30)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    added, updated = 0, 0
    for emp in root.findall("employee"):
        iiko_uuid = (emp.findtext("id") or "").strip()
        name      = (emp.findtext("name") or "").strip()
        if not iiko_uuid or not name:
            continue
        existing = db.query(Supplier).filter(Supplier.iiko_uuid == iiko_uuid).first()
        if existing:
            existing.name = name
            updated += 1
        else:
            db.add(Supplier(iiko_uuid=iiko_uuid, name=name))
            added += 1

    db.commit()
    return {"added": added, "updated": updated}


@router.get("/suppliers")
def list_suppliers(db: Session = Depends(get_db), _=Depends(require_co)):
    return [
        {"id": s.id, "iiko_uuid": s.iiko_uuid, "name": s.name}
        for s in db.query(Supplier).order_by(Supplier.name).all()
    ]


@router.post("/iiko/sync-stores")
def sync_stores(db: Session = Depends(get_db), _=Depends(require_co)):
    """Загружает склады из IIKO → проставляет store_id ресторанам."""
    restaurant = db.query(Restaurant).filter(Restaurant.is_active == True).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Нет активных ресторанов")

    key = get_session_key(db, restaurant)
    r = requests.get(
        f"{restaurant.base_url}/resto/api/corporation/stores",
        params={"key": key, "revisionFrom": -1},
        timeout=60,
    )
    r.raise_for_status()

    root = ET.fromstring(r.text)
    stores = []
    for item in root.findall(".//corporateItemDto"):
        if (item.findtext("type") or "").strip().upper() != "STORE":
            continue
        stores.append({
            "store_id":   (item.findtext("id")   or "").strip(),
            "store_code": (item.findtext("code")  or "").strip(),
            "store_name": (item.findtext("name")  or "").strip(),
        })

    rest_map = {rest.code: rest for rest in db.query(Restaurant).all()}
    matched = 0
    for store in stores:
        rest = rest_map.get(store["store_code"].strip())
        if rest and not rest.store_id:
            rest.store_id = store["store_id"]
            matched += 1

    db.commit()
    return {"stores_found": len(stores), "restaurants_matched": matched, "stores": stores}


# ════════════════════════════════════════════════════════════════
# ЕЖЕМЕСЯЧНАЯ ЗАГРУЗКА mapping_ABL.xlsx
# ════════════════════════════════════════════════════════════════

@router.post("/upload-mapping-abl")
async def upload_mapping_abl(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Загружает новый прайс-лист mapping_ABL.xlsx → обновляет abl_products."""
    import pandas as pd

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Только Excel файлы (.xlsx, .xls)")

    file_bytes = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Не удалось прочитать файл: {e}")

    # Нормализуем опечатку "Основоной" → "Основной"
    df.columns = [c.replace("Основоной", "Основной") for c in df.columns]

    required = ["Артикул ABL", "Основной артикул ABL", "Артикул айко", "Наименование"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Не найдены колонки: {missing}. Колонки файла: {df.columns.tolist()}",
        )

    product_num_map = {p.product_num: p.id for p in db.query(ProductCatalog).all()}
    existing_map    = {p.abl_article: p for p in db.query(AblProduct).all()}

    added = updated = skipped = 0
    for _, row in df.iterrows():
        abl_art  = str(row.get("Артикул ABL", "")).strip()
        if not abl_art or abl_art == "nan":
            skipped += 1
            continue

        main_art = str(row.get("Основной артикул ABL", "")).strip()
        iiko_art = str(row.get("Артикул айко", "")).strip()
        name     = str(row.get("Наименование", "")).strip()
        supplier = str(row.get("Поставщик", "")).strip() if "Поставщик" in df.columns else ""

        def _f(col):
            try:
                return float(row[col]) if col in df.columns else None
            except (ValueError, TypeError):
                return None

        price     = _f("Цена продажи")
        price_vat = _f("Цена продажи с НДС")
        product_catalog_id = product_num_map.get(iiko_art)

        existing = existing_map.get(abl_art)
        if existing:
            existing.abl_main_article   = main_art
            existing.name               = name
            existing.supplier           = supplier or existing.supplier
            existing.price              = price if price is not None else existing.price
            existing.price_vat          = price_vat if price_vat is not None else existing.price_vat
            existing.product_catalog_id = product_catalog_id
            updated += 1
        else:
            db.add(AblProduct(
                abl_article=abl_art, abl_main_article=main_art,
                name=name, supplier=supplier,
                price=price, price_vat=price_vat,
                product_catalog_id=product_catalog_id,
            ))
            added += 1

    db.commit()
    total_in_db  = db.query(AblProduct).count()
    linked       = db.query(AblProduct).filter(AblProduct.product_catalog_id.isnot(None)).count()
    return {
        "added": added, "updated": updated, "skipped": skipped,
        "total_in_db": total_in_db,
        "linked_to_iiko": linked,
        "not_linked": total_in_db - linked,
    }


# ════════════════════════════════════════════════════════════════
# IIKO SYNC — СЧЕТА СПИСАНИЯ
# ════════════════════════════════════════════════════════════════

@router.post("/iiko/sync-accounts/{restaurant_id}")
def sync_accounts_from_iiko(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Загружает счета затрат из IIKO → таблица accounts."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    key = get_session_key(db, restaurant)

    # Пробуем стандартный эндпоинт счетов IIKO
    r = requests.get(
        f"{restaurant.base_url}/resto/api/corporation/accounts",
        params={"key": key, "revisionFrom": -1},
        timeout=60,
    )
    r.raise_for_status()

    root = ET.fromstring(r.text)
    added, updated, skipped = 0, 0, 0

    # IIKO возвращает corporateItemDto с type=ACCOUNT
    items = root.findall(".//corporateItemDto")
    if not items:
        items = root.findall(".//accountItem")

    for item in items:
        item_type = (item.findtext("type") or "").strip().upper()
        # Берём все счета затрат (ACCOUNT или EXPENSE)
        if item_type not in ("ACCOUNT", "EXPENSE_ACCOUNT", ""):
            if item_type and item_type not in ("ACCOUNT",):
                skipped += 1
                continue

        iiko_uuid = (item.findtext("id") or "").strip()
        name      = (item.findtext("name") or "").strip()
        if not iiko_uuid or not name:
            skipped += 1
            continue

        from app.models.catalog import Account as AccountModel
        existing = db.query(AccountModel).filter(AccountModel.account_iiko_id == iiko_uuid).first()
        if existing:
            existing.name = name
            updated += 1
        else:
            db.add(AccountModel(account_iiko_id=iiko_uuid, name=name))
            added += 1

    db.commit()
    total = db.query(Account).count()
    return {"added": added, "updated": updated, "skipped": skipped, "total": total}


# ════════════════════════════════════════════════════════════════
# IIKO SYNC — КАТАЛОГ ТОВАРОВ
# ════════════════════════════════════════════════════════════════

@router.post("/iiko/sync-catalog/{restaurant_id}")
def sync_catalog_from_iiko(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Загружает номенклатуру из IIKO → таблица product_catalog.
    Включая удалённые товары (is_deleted=True) — для полной связи с техкартами.
    Новые товары без группы попадают в группу UNMAPPED.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    key = get_session_key(db, restaurant)

    # Группа UNMAPPED — для товаров без назначенной группы
    from app.models.catalog import ProductGroup as PG
    unmapped_group = db.query(PG).filter(PG.name == "UNMAPPED").first()
    unmapped_group_id = unmapped_group.id if unmapped_group else None

    # IIKO v2 endpoint — includeDeleted:true чтобы получить и удалённые товары
    r = requests.get(
        f"{restaurant.base_url}/resto/api/v2/entities/products/list",
        params={"key": key, "includeDeleted": "true"},
        timeout=120,
    )
    r.raise_for_status()
    products = r.json()

    existing_map = {p.product_iiko_id: p for p in db.query(ProductCatalog).all()}

    added, updated, skipped = 0, 0, 0
    import re as _re

    for prod in products:
        iiko_id = (prod.get("id") or "").strip()
        if not iiko_id:
            skipped += 1
            continue

        # Фильтр: только товары типа GOODS (не блюда, модификаторы, услуги)
        if prod.get("type", "").upper() != "GOODS":
            skipped += 1
            continue

        is_deleted = bool(prod.get("deleted", False))

        code    = str(prod.get("code") or "").strip()
        article = str(prod.get("num")  or "").strip()
        name    = str(prod.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        # Единица измерения
        unit_type = ""
        main_unit = prod.get("mainUnit") or {}
        if isinstance(main_unit, dict):
            raw_name = main_unit.get("name") or ""
            if raw_name and not _re.match(r'^[0-9a-f-]{36}$', raw_name.lower()):
                unit_type = raw_name
        elif isinstance(main_unit, str):
            if main_unit and not _re.match(r'^[0-9a-f-]{36}$', main_unit.lower()):
                unit_type = main_unit
        unit_type = unit_type[:100] if unit_type else ""

        existing = existing_map.get(iiko_id)
        if existing:
            existing.name       = name
            existing.is_deleted = is_deleted
            if code:    existing.product_num     = code
            if article: existing.product_article = article
            if unit_type: existing.unit_type     = unit_type
            updated += 1
        else:
            db.add(ProductCatalog(
                product_iiko_id=iiko_id,
                product_num=code or iiko_id[:8],
                product_article=article or None,
                name=name,
                group_id=unmapped_group_id,   # UNMAPPED вместо NULL
                unit_type=unit_type or None,
                is_deleted=is_deleted,
            ))
            added += 1

    db.commit()

    # Перелинковываем chart_ingredients после синка каталога
    from sqlalchemy import text
    db.execute(text("""
        UPDATE chart_ingredients ci
        SET product_catalog_id = pc.id
        FROM product_catalog pc
        WHERE ci.ingredient_iiko_uuid = pc.product_iiko_id
          AND ci.product_catalog_id IS NULL
    """))
    db.commit()

    total    = db.query(ProductCatalog).count()
    unmapped = db.query(ProductCatalog).filter(ProductCatalog.group_id == unmapped_group_id).count()
    deleted  = db.query(ProductCatalog).filter(ProductCatalog.is_deleted == True).count()
    return {
        "added": added, "updated": updated, "skipped": skipped,
        "total": total, "unmapped": unmapped, "deleted_in_iiko": deleted,
    }


# ════════════════════════════════════════════════════════════════
# РЕДАКТИРОВАНИЕ ТОВАРА (смена группы)
# ════════════════════════════════════════════════════════════════

class UpdateProductRequest(BaseModel):
    group_id: Optional[int] = None
    product_num: Optional[str] = None
    unit_type: Optional[str] = None


@router.patch("/product-catalog/{product_id}")
def update_product_catalog(
    product_id: int,
    body: UpdateProductRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    p = db.query(ProductCatalog).filter(ProductCatalog.id == product_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Товар не найден")
    if "group_id" in body.model_fields_set:
        p.group_id = body.group_id
    if body.product_num is not None:
        p.product_num = body.product_num.strip()
    if body.unit_type is not None:
        p.unit_type = body.unit_type.strip() or None
    db.commit()
    return {"id": p.id, "product_num": p.product_num, "name": p.name, "group_id": p.group_id}


# ════════════════════════════════════════════════════════════════
# МАТРИЦА НОРМ (все группы × все рестораны)
# ════════════════════════════════════════════════════════════════

@router.get("/waste-rates/matrix")
def get_waste_rates_matrix(db: Session = Depends(get_db), _=Depends(require_co)):
    """Возвращает матрицу норм: группы × рестораны."""
    restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).order_by(Restaurant.code).all()
    groups = db.query(ProductGroup).order_by(ProductGroup.name).all()
    rates = db.query(WasteRate).all()

    rates_map = {}
    for r in rates:
        rates_map[(r.restaurant_id, r.group_id)] = r.rate_pct

    return {
        "restaurants": [{"id": r.id, "code": r.code, "name": r.name} for r in restaurants],
        "groups": [{"id": g.id, "name": g.name} for g in groups],
        "rates": {
            f"{r_id}_{g_id}": pct
            for (r_id, g_id), pct in rates_map.items()
        },
    }


class RateCell(BaseModel):
    restaurant_id: int
    group_id: int
    rate_pct: float


@router.put("/waste-rates/matrix")
def save_waste_rates_matrix(
    rates: List[RateCell],
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Bulk-сохранение норм из матрицы."""
    for cell in rates:
        existing = db.query(WasteRate).filter(
            WasteRate.restaurant_id == cell.restaurant_id,
            WasteRate.group_id == cell.group_id,
        ).first()
        if existing:
            existing.rate_pct = cell.rate_pct
        else:
            db.add(WasteRate(
                restaurant_id=cell.restaurant_id,
                group_id=cell.group_id,
                rate_pct=cell.rate_pct,
            ))
    db.commit()
    return {"saved": len(rates)}


# ════════════════════════════════════════════════════════════════
# ПРЕСЕТЫ (preset_definitions) — независимое управление
# ════════════════════════════════════════════════════════════════

class CreatePresetRequest(BaseModel):
    preset_type: str   # sales | writeoff | inventory | revenue_net | complete_waste
    preset_uuid: str
    description: Optional[str] = None


class UpdatePresetRequest(BaseModel):
    preset_type: Optional[str] = None
    preset_uuid: Optional[str] = None
    description: Optional[str] = None


def _preset_dict(p: PresetDefinition, db: Session) -> dict:
    restaurants = db.query(Restaurant).filter(
        Restaurant.presets.any(PresetDefinition.id == p.id)
    ).all()
    return {
        "id": p.id,
        "preset_type": p.preset_type,
        "preset_uuid": p.preset_uuid,
        "description": p.description,
        "restaurants": [{"id": r.id, "code": r.code, "name": r.name} for r in restaurants],
    }


@router.get("/presets")
def list_presets(db: Session = Depends(get_db), _=Depends(require_co)):
    presets = db.query(PresetDefinition).order_by(
        PresetDefinition.preset_type, PresetDefinition.id
    ).all()
    return [_preset_dict(p, db) for p in presets]


@router.post("/presets", status_code=201)
def create_preset(body: CreatePresetRequest, db: Session = Depends(get_db), _=Depends(require_co)):
    existing = db.query(PresetDefinition).filter(
        PresetDefinition.preset_type == body.preset_type,
        PresetDefinition.preset_uuid == body.preset_uuid.strip(),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Пресет с таким типом и UUID уже существует")
    p = PresetDefinition(
        preset_type=body.preset_type,
        preset_uuid=body.preset_uuid.strip(),
        description=body.description,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _preset_dict(p, db)


@router.patch("/presets/{preset_id}")
def update_preset(
    preset_id: int,
    body: UpdatePresetRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    p = db.query(PresetDefinition).filter(PresetDefinition.id == preset_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Пресет не найден")
    if body.preset_type is not None:
        p.preset_type = body.preset_type
    if body.preset_uuid is not None:
        p.preset_uuid = body.preset_uuid.strip()
    if "description" in body.model_fields_set:
        p.description = body.description
    db.commit()
    return _preset_dict(p, db)


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(preset_id: int, db: Session = Depends(get_db), _=Depends(require_co)):
    p = db.query(PresetDefinition).filter(PresetDefinition.id == preset_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Пресет не найден")
    # Отвязываем от всех ресторанов
    p.restaurants = []
    db.flush()
    db.delete(p)
    db.commit()


@router.get("/restaurants/{restaurant_id}/presets")
def get_restaurant_presets(
    restaurant_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    return [{"id": p.id, "preset_type": p.preset_type, "preset_uuid": p.preset_uuid, "description": p.description}
            for p in r.presets]


class AssignPresetsRequest(BaseModel):
    preset_ids: List[int]


@router.put("/restaurants/{restaurant_id}/presets")
def assign_presets_to_restaurant(
    restaurant_id: int,
    body: AssignPresetsRequest,
    db: Session = Depends(get_db),
    _=Depends(require_co),
):
    """Назначить список пресетов ресторану (заменяет текущие)."""
    r = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    presets = db.query(PresetDefinition).filter(PresetDefinition.id.in_(body.preset_ids)).all()
    r.presets = presets
    db.commit()
    return {"restaurant_id": restaurant_id, "preset_ids": [p.id for p in presets]}
