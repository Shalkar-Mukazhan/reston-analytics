from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.database import get_db
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, get_current_user
from app.models.user import User
from app.models.audit import AuditLog

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str
    username: str


class RefreshRequest(BaseModel):
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(
        User.username == form_data.username.strip().lower(),
        User.is_active == True,
    ).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        db.add(AuditLog(
            action="login_failed",
            details=f"username={form_data.username}",
            ip_address=request.client.host,
        ))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    db.add(AuditLog(
        user_id=user.id,
        action="login",
        ip_address=request.client.host,
    ))
    db.commit()

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
        role=user.role,
        username=user.username,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный refresh токен")

    user = db.query(User).filter(User.id == int(payload.get("sub")), User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
        role=user.role,
        username=user.username,
    )


@router.get("/me")
def me(current_user: User = Depends(get_current_user), db=Depends(get_db)):
    from sqlalchemy import text as sa_text
    rows = db.execute(sa_text("SELECT key, value FROM system_settings")).fetchall()
    settings = {r[0]: r[1] for r in rows}
    return {
        "id": current_user.id,
        "username": current_user.username,
        "role": current_user.role,
        "settings": settings,
        "restaurants": [
            {
                "id": r.id,
                "code": r.code,
                "name": r.name,
                "feat_invoices":  r.feat_invoices  if r.feat_invoices  is not None else True,
                "feat_invoices2": r.feat_invoices2 if r.feat_invoices2 is not None else True,
                "feat_analytics": r.feat_analytics if r.feat_analytics is not None else True,
                "feat_reports":   r.feat_reports   if r.feat_reports   is not None else True,
                "feat_planning":  r.feat_planning  if r.feat_planning  is not None else True,
                "feat_checklist": r.feat_checklist if r.feat_checklist is not None else True,
                "feat_about":     r.feat_about     if r.feat_about     is not None else True,
                "google_sheet_url": r.google_sheet_url,
            }
            for r in current_user.restaurants
        ],
    }
