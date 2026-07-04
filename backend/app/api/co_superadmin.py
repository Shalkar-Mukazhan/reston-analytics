from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone
import os

from app.core.database import get_db
from app.core.security import hash_password
from app.models.co_models import CoTenant, CoUser, CoSubscription

router = APIRouter(prefix="/api/superadmin", tags=["superadmin"])

SUPERADMIN_SECRET = os.environ.get("SUPERADMIN_SECRET", "")


def _require_superadmin(x_superadmin_secret: str = Header(...)):
    """Простая защита через секретный заголовок."""
    if not SUPERADMIN_SECRET:
        raise HTTPException(500, "SUPERADMIN_SECRET не настроен")
    if x_superadmin_secret != SUPERADMIN_SECRET:
        raise HTTPException(403, "Неверный суперадмин-секрет")


class CreateTenantRequest(BaseModel):
    slug: str              # напр. "coffee-original-2"
    name: str              # напр. "Coffee Original 2"
    type: str = "chain"    # "chain" или "freelancer"
    plan: str = "pro"      # "trial", "start", "pro", "unlimited"
    admin_email: str
    admin_name: str
    admin_password: str


class TenantResponse(BaseModel):
    tenant_id: int
    slug: str
    name: str
    type: str
    plan: str
    admin_user_id: int
    admin_email: str


@router.post(
    "/tenants",
    response_model=TenantResponse,
    dependencies=[Depends(_require_superadmin)],
    summary="Создать нового тенанта + первого admin-пользователя"
)
def create_tenant(body: CreateTenantRequest, db: Session = Depends(get_db)):
    # Проверить уникальность slug
    existing = db.query(CoTenant).filter(CoTenant.slug == body.slug).first()
    if existing:
        raise HTTPException(400, f"Тенант с slug '{body.slug}' уже существует")

    # Создать тенант
    tenant = CoTenant(
        slug=body.slug,
        name=body.name,
        type=body.type,
        plan=body.plan,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    db.flush()  # получаем tenant.id без коммита

    # Проверить уникальность email внутри тенанта
    email_exists = db.query(CoUser).filter(
        CoUser.tenant_id == tenant.id,
        CoUser.email == body.admin_email
    ).first()
    if email_exists:
        raise HTTPException(400, "Email уже занят")

    # Создать первого admin-пользователя
    admin = CoUser(
        tenant_id=tenant.id,
        email=body.admin_email,
        name=body.admin_name,
        password_hash=hash_password(body.admin_password),
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(tenant)
    db.refresh(admin)

    return TenantResponse(
        tenant_id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        type=tenant.type,
        plan=tenant.plan,
        admin_user_id=admin.id,
        admin_email=admin.email,
    )


@router.get(
    "/tenants",
    dependencies=[Depends(_require_superadmin)],
    summary="Список всех тенантов"
)
def list_tenants(db: Session = Depends(get_db)):
    tenants = db.query(CoTenant).order_by(CoTenant.id).all()
    return [
        {
            "id": t.id,
            "slug": t.slug,
            "name": t.name,
            "type": t.type,
            "plan": t.plan,
            "is_active": t.is_active,
        }
        for t in tenants
    ]


@router.patch(
    "/tenants/{tenant_id}",
    dependencies=[Depends(_require_superadmin)],
    summary="Обновить план/статус тенанта"
)
def update_tenant(
    tenant_id: int,
    plan: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    tenant = db.query(CoTenant).filter(CoTenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(404, "Тенант не найден")
    if plan is not None:
        tenant.plan = plan
        # Синхронизировать subscriptions
        subscription = db.query(CoSubscription).filter(
            CoSubscription.tenant_id == tenant_id
        ).order_by(CoSubscription.id.desc()).first()

        if subscription:
            subscription.plan = plan
            subscription.status = "active"
            subscription.trial_ends_at = None
            subscription.expires_at = None
        else:
            new_sub = CoSubscription(
                tenant_id=tenant_id,
                plan=plan,
                status="active",
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_sub)
    if is_active is not None:
        tenant.is_active = is_active
    db.commit()
    return {"id": tenant.id, "slug": tenant.slug, "plan": tenant.plan, "is_active": tenant.is_active}
