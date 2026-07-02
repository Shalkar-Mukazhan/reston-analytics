from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import httpx, os

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.co_models import CoUser, CoTenant, CoSubscription, CoGoogleOAuth

router = APIRouter(prefix="/api/auth/google", tags=["google-oauth"])

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI",
                              "https://reston.kz/api/auth/google/callback")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@router.get("/login", summary="Редирект на Google OAuth")
def google_login():
    params = (
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
    )
    return RedirectResponse(GOOGLE_AUTH_URL + params)


@router.get("/callback", summary="Callback от Google")
def google_callback(code: str, db: Session = Depends(get_db)):
    # 1. Обменять code на токен
    with httpx.Client() as client:
        token_resp = client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(400, "Ошибка получения токена Google")
        token_data = token_resp.json()

        # 2. Получить данные пользователя
        user_resp = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(400, "Ошибка получения данных пользователя")
        guser = user_resp.json()

    google_sub = guser["sub"]
    google_email = guser["email"]
    google_name = guser.get("name", "")

    # 3. Найти существующую связку Google → User
    oauth_record = db.query(CoGoogleOAuth).filter(
        CoGoogleOAuth.google_sub == google_sub
    ).first()

    if oauth_record:
        # Пользователь уже регался через Google — просто логиним
        user = db.query(CoUser).filter(
            CoUser.id == oauth_record.user_id,
            CoUser.is_active == True
        ).first()
        if not user:
            raise HTTPException(401, "Пользователь деактивирован")
    else:
        # Новый пользователь — ищем по email
        user = db.query(CoUser).filter(
            CoUser.email == google_email
        ).first()

        if user:
            # Email уже есть в системе — привязываем Google к существующему
            oauth_record = CoGoogleOAuth(
                user_id=user.id,
                google_sub=google_sub,
                email=google_email,
                name=google_name,
                created_at=datetime.now(timezone.utc)
            )
            db.add(oauth_record)
            db.commit()
        else:
            # Совсем новый — создаём тенант + юзера + подписку
            import secrets
            tenant = CoTenant(
                slug=f"user-{secrets.token_hex(4)}",
                name=google_name or google_email.split("@")[0],
                type="freelancer",
                plan="trial",
                is_active=True,
                created_at=datetime.now(timezone.utc)
            )
            db.add(tenant)
            db.flush()

            user = CoUser(
                tenant_id=tenant.id,
                email=google_email,
                name=google_name or google_email.split("@")[0],
                password_hash=hash_password(secrets.token_hex(16)),
                role="admin",
                is_active=True,
            )
            db.add(user)
            db.flush()

            # Подписка trial — 14 дней
            subscription = CoSubscription(
                tenant_id=tenant.id,
                plan="trial",
                status="active",
                trial_ends_at=datetime.now(timezone.utc) + timedelta(days=14),
                created_at=datetime.now(timezone.utc)
            )
            db.add(subscription)

            oauth_record = CoGoogleOAuth(
                user_id=user.id,
                google_sub=google_sub,
                email=google_email,
                name=google_name,
                created_at=datetime.now(timezone.utc)
            )
            db.add(oauth_record)
            db.commit()
            db.refresh(user)

    # 4. Создать JWT и редиректнуть на фронт
    payload = {
        "sub": str(user.id),
        "tenant": "co",
        "tenant_id": user.tenant_id
    }
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    # Редирект на фронт с токенами в URL
    frontend_url = (
        f"https://reston.kz/auth/callback"
        f"?access_token={access_token}"
        f"&refresh_token={refresh_token}"
    )
    return RedirectResponse(frontend_url)
