from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import hashlib, httpx

from app.core.database import get_db
from app.api.co_auth import get_current_co_user
from app.models.co_models import (
    CoUser, CoTenant, CoIikoConnection, CoRestaurant, CoUserRestaurant
)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class CompanyData(BaseModel):
    company_name: str
    phone: str
    tenant_type: str  # "freelancer" или "chain"


class IikoData(BaseModel):
    name: str        # название (напр. "Основной сервер")
    base_url: str    # напр. "https://xxx.iiko.it"
    login: str
    password: str


# Шаг 1 онбординга — сохранить данные компании
@router.post("/company")
def save_company(
    body: CompanyData,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user)
):
    tenant = db.query(CoTenant).filter(
        CoTenant.id == user.tenant_id
    ).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")

    tenant.company_name = body.company_name
    tenant.phone = body.phone
    tenant.type = body.tenant_type
    db.commit()
    return {"ok": True}


# Шаг 2 — тест подключения iiko
@router.post("/iiko/test")
def test_iiko(
    body: IikoData,
    user: CoUser = Depends(get_current_co_user)
):
    # SHA1 хэш пароля (требование iiko API)
    password_sha1 = hashlib.sha1(
        body.password.encode()
    ).hexdigest()

    base_url = body.base_url.rstrip("/")
    url = (f"{base_url}/resto/api/auth"
           f"?login={body.login}"
           f"&pass={password_sha1}")

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(url)
        if resp.status_code == 200 and len(resp.text) > 10:
            return {"ok": True, "message": "Подключение успешно"}
        else:
            return {"ok": False,
                    "message": "Неверный логин или пароль iiko"}
    except Exception as e:
        return {"ok": False,
                "message": f"Сервер недоступен: {str(e)}"}


# Шаг 2 — сохранить iiko подключение (upsert — один connection на тенанта)
@router.post("/iiko/save")
def save_iiko(
    body: IikoData,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user)
):
    password_sha1 = hashlib.sha1(
        body.password.encode()
    ).hexdigest()

    conn = db.query(CoIikoConnection).filter(
        CoIikoConnection.tenant_id == user.tenant_id
    ).first()

    if conn:
        conn.name = body.name
        conn.base_url = body.base_url.rstrip("/")
        conn.login = body.login
        conn.password_hash = password_sha1
        conn.is_active = True
    else:
        conn = CoIikoConnection(
            tenant_id=user.tenant_id,
            name=body.name,
            base_url=body.base_url.rstrip("/"),
            login=body.login,
            password_hash=password_sha1,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(conn)

    db.commit()
    db.refresh(conn)
    return {"ok": True, "connection_id": conn.id}


# Шаг 3 — завершить онбординг
@router.post("/complete")
def complete_onboarding(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user)
):
    tenant = db.query(CoTenant).filter(
        CoTenant.id == user.tenant_id
    ).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")

    tenant.onboarding_complete = True

    # Мост онбординг → первый ресторан: если у тенанта есть активное iiko-
    # подключение, но ещё нет ни одного ресторана — создать ресторан "main"
    # из данных подключения, иначе после онбординга экран будет пустым
    # (рабочий код читает base_url/iiko_login/iiko_password_hash из CoRestaurant,
    # а не из iiko_connections).
    conn = db.query(CoIikoConnection).filter(
        CoIikoConnection.tenant_id == user.tenant_id,
        CoIikoConnection.is_active == True,
        CoIikoConnection.base_url != ""
    ).first()

    existing = db.query(CoRestaurant).filter(
        CoRestaurant.tenant_id == user.tenant_id
    ).first()

    restaurant_created = conn is not None and existing is None

    if conn and not existing:
        restaurant = CoRestaurant(
            tenant_id=user.tenant_id,
            code="main",
            name=tenant.company_name or tenant.name,
            base_url=conn.base_url,
            iiko_login=conn.login,
            iiko_password_hash=conn.password_hash,
            is_active=True,
        )
        db.add(restaurant)
        db.flush()

        user_rest = CoUserRestaurant(
            user_id=user.id,
            restaurant_id=restaurant.id
        )
        db.add(user_rest)

    db.commit()
    return {
        "ok": True,
        "restaurant_created": restaurant_created,
    }


# Получить статус онбординга
@router.get("/status")
def get_status(
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user)
):
    tenant = db.query(CoTenant).filter(
        CoTenant.id == user.tenant_id
    ).first()

    connections = db.query(CoIikoConnection).filter(
        CoIikoConnection.tenant_id == user.tenant_id,
        CoIikoConnection.is_active == True
    ).all()

    return {
        "onboarding_complete": tenant.onboarding_complete,
        "company_name": tenant.company_name,
        "phone": tenant.phone,
        "iiko_connected": len(connections) > 0,
        "connections_count": len(connections)
    }
