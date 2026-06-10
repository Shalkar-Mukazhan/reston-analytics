import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api import auth, reports, writeoff, analytics, admin, invoices, dashboard, recipes, planning, checklist, invoices2
from app.api import co_auth, co_admin, co_invoices, co_writeoffs

# Sentry — мониторинг ошибок (включается если задан SENTRY_DSN)
_sentry_dsn = os.environ.get("SENTRY_DSN", "")
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
        environment=os.environ.get("APP_ENV", "production"),
    )

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="RestOn Analytics API",
    description="Система аналитики и контроля ресторанов I'M",
    version="2.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_origins = ["https://reston.kz", "https://www.reston.kz"]
_extra_origins = os.environ.get("EXTRA_CORS_ORIGINS", "")
if _extra_origins:
    _cors_origins += [o.strip() for o in _extra_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(writeoff.router)
app.include_router(analytics.router)
app.include_router(admin.router)
app.include_router(invoices.router)
app.include_router(dashboard.router)
app.include_router(recipes.router)
app.include_router(planning.router)
app.include_router(checklist.router)
app.include_router(invoices2.router)
app.include_router(co_auth.router)
app.include_router(co_admin.router)
app.include_router(co_invoices.router)
app.include_router(co_writeoffs.router)


@app.get("/health")
def health():
    return {"status": "ok"}
