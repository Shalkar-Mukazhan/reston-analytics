"""Auth API for coffee_original tenant."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.models.co_models import CoUser

router = APIRouter(prefix="/api/co/auth", tags=["co-auth"])

_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/co/auth/login")


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    name: str


class RefreshRequest(BaseModel):
    refresh_token: str


def get_current_co_user(token: str = Depends(_oauth2), db: Session = Depends(get_db)) -> CoUser:
    payload = decode_token(token)
    if payload.get("tenant") != "co":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")
    user_id = int(payload.get("sub", 0))
    user = db.query(CoUser).filter(CoUser.id == user_id, CoUser.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    tok_tid = payload.get("tenant_id")
    if tok_tid is not None and user.tenant_id != tok_tid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не соответствует тенанту пользователя",
        )
    return user


def require_co_admin(user: CoUser = Depends(get_current_co_user)) -> CoUser:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Требуются права администратора")
    return user


def _make_tokens(user: CoUser) -> TokenResponse:
    payload = {"sub": str(user.id), "tenant": "co", "tenant_id": user.tenant_id}
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
        role=user.role,
        name=user.name,
    )


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(CoUser).filter(
        CoUser.email == form_data.username.strip().lower(),
        CoUser.is_active == True,
    ).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    return _make_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh" or payload.get("tenant") != "co":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh токен")
    user_id = int(payload.get("sub", 0))
    user = db.query(CoUser).filter(CoUser.id == user_id, CoUser.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return _make_tokens(user)


@router.get("/me")
def me(user: CoUser = Depends(get_current_co_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "restaurant_ids": [r.id for r in user.restaurants],
    }


# ── Bootstrap: create first admin user ─────────────────────────────────────

class CreateFirstAdminRequest(BaseModel):
    email: str
    name: str
    password: str
    secret: str


@router.post("/bootstrap", status_code=201)
def bootstrap(body: CreateFirstAdminRequest, db: Session = Depends(get_db)):
    """Create the first CO admin. Only works if no users exist yet."""
    import os
    expected = os.environ.get("CO_BOOTSTRAP_SECRET", "")
    if not expected or body.secret != expected:
        raise HTTPException(status_code=403, detail="Неверный секрет")
    if db.query(CoUser).count() > 0:
        raise HTTPException(status_code=409, detail="Пользователи уже существуют")
    user = CoUser(
        email=body.email.strip().lower(),
        name=body.name.strip(),
        password_hash=hash_password(body.password),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "email": user.email, "role": user.role}
