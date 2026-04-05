import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, reports, writeoff, analytics, admin, invoices, dashboard, recipes, planning, checklist

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

app = FastAPI(
    title="Reston Analytics API",
    description="Система аналитики и контроля ресторанов I'M",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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


@app.get("/health")
def health():
    return {"status": "ok"}
