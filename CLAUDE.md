# CLAUDE.md — RestOn / Coffee Original

Состояние на 2026-06-21. Проект обслуживает одного клиента — **Coffee Original (CO)**.
Старый код «Reston» вырезан рефакторингом (см. git `be89c9a`), осталась только CO-логика.
Идёт перевод на **мультитенантность (SaaS)** — см. раздел ниже. Alembic head: `0055`.

---

## Что это

Веб-система учёта для сети кофеен Coffee Original (17 ресторанов): накладные (OCR),
акты списания, синхронизация справочников с iiko. Прод: `https://reston.kz`
(домен исторический, не переименован), сервер `185.98.7.66`, папка `/opt/reston`.

Стек: FastAPI (backend) + React/Vite (frontend) + Celery/Redis + PostgreSQL 14.
Подробная дока CO: `docs/coffee_original.md`.

---

## ⚠️ Инфраструктура — читать ПЕРЕД любым изменением

**Реальная БД живёт на ХОСТЕ, не в контейнере.** Backend ходит на
`DATABASE_URL=...@172.17.0.1:5432/wastecontrol` (PostgreSQL 14, установлен прямо на сервере).
С хоста: `PGPASSFILE=/root/.pgpass psql -h 127.0.0.1 -U wastecontrol_user -d wastecontrol`.
Контейнер `reston-postgres-1` (postgres:16) — **пустой, прод им не пользуется** (см. «Осталось»).

**Прод — гибрид из ДВУХ compose-файлов** под одним проектом `reston`:
- из `docker-compose.prod.yml`: `nginx`, `backend` (код **впечён** в образ), `postgres`, `redis`
- из `docker-compose.yml` (DEV): `frontend` (Vite :5173), `celery`, `celery-beat`
  — у этих троих `./backend`/`./frontend` смонтированы **живьём** (код подхватывается рестартом)

nginx проксирует `backend:8000` и `frontend:5173`.

**🔴 Железные правила деплоя:**
- `docker compose` (v2 plugin) на сервере НЕ работает. Использовать бинарь **`docker-compose`** (= v2.24.0).
- Любой `up` — **ТОЛЬКО `--no-deps` + явное имя сервиса**. Без `--no-deps` compose поднимет
  prod-frontend (Dockerfile.prod, nginx :80, без `command`) поверх рабочего dev-frontend →
  nginx ждёт :5173 → **каскад, сайт ляжет (502)**.
- Backend код **впечён** → правка `.py` требует `build` + `up -d --no-deps backend`
  (просто `restart` не подхватит). celery/celery-beat — код живой через mount.
- requirements.txt меняет **3 раздельных образа** (`reston-backend`, `reston-celery`,
  `reston-celery-beat`) → пересобирать все три (backend prod-файлом, celery/beat dev-файлом).
- Если frontend сломался: `docker-compose -f docker-compose.yml up -d frontend`.

---

## ✅ Сделано (2026-06-14 … 06-15)

- **SSL reston.kz** — авто-продление через certbot **webroot** + deploy-хук (reload nginx без простоя).
  Таймер `snap.certbot.renew.timer` активен. Конфиг nginx: ACME-challenge в `location /` (не на server).
- **Автобэкапы хост-БД** — починены. Скрипт `scripts/backup_host_db.sh` (pg_dump -Fc, проверка
  целостности, ротация), cron `/etc/cron.d/coffee-original-backup` ежедневно 03:30 UTC, дампы в
  `backups/host/`. Восстановление проверено. Старый контейнер `db-backup` (бэкапил пустую БД) убран.
- **Legacy-схема `public` УДАЛЕНА** (33 таблицы старого reston, было ~52 MB). БД 64 MB → 11 MB.
  Бэкап перед дропом: `backups/manual/public_before_drop_*.dump`. Осталась только схема
  `coffee_original` (18 рабочих таблиц + `alembic_version`).
- **env.py исправлен** — `version_table_schema="coffee_original"` в обоих `context.configure`
  (таблицу `alembic_version` перенесли из public в coffee_original). `alembic current` → `0052` (head).
- **Мёртвый код (A3)** — из `app/core/security.py` удалены `get_current_user`, `require_co`,
  `require_co_or_admin` (ссылались на несуществующий `app.models.user`). Живая авторизация —
  `get_current_co_user`/`require_co_admin` в `app/api/co_auth.py`.

---

## 🔲 Осталось

- **A4 — чистка `requirements.txt`** (отдельная задача с пересборкой 3 образов):
  удалить `gspread`, `google-auth`, `reportlab`, `tenacity`, `openpyxl` (0 импортов).
  🔴 `httpx` НЕ трогать — нужен `anthropic`. Заодно убрать осиротевшие импорты в `security.py`
  (`Depends`, `Session`, `get_db`, `OAuth2PasswordBearer`, `oauth2_scheme`).
- **Пустой контейнер `postgres`** — убрать. Но у `backend` и `celery` в prod-файле
  `depends_on: postgres: service_healthy` (гейт старта) → сперва снять depends_on, потом
  точечно `stop/rm`. Освободит volume ~47 MB.
- **Привести compose к реальности** — dev/prod рассинхронизированы (prod-frontend без command,
  postgres-гейт). Опционально: один честный файл, отражающий фактический деплой.
- **SaaS / мульти-тенантность** — в активной работе, см. раздел **«Мультитенантность (SaaS)»** ниже.
  Осталось по этой цели: `co_admin.py`, суперадмин-роутер, регистрация/онбординг, биллинг,
  убрать хардкод «RestOn»/reston.kz из main.py/index.html.

---

## Мультитенантность (SaaS)

Перевод со «схема-на-клиента» на shared-schema + `tenant_id`. Coffee Original = `tenant_id=1`.

### Порядок работ (статусы)

- ✅ Миграция `0053` — таблица `tenants`, Coffee Original = `id=1`
- ✅ Миграция `0054` — `tenant_id` (nullable) во всех 8 таблицах + backfill=1 + индексы
- ✅ Миграция `0055` — NOT NULL + 5 составных UNIQUE + PK `co_settings` = `(tenant_id, key)`
- ✅ JWT — `tenant_id` в payload + сверка в `get_current_co_user` + `/me` возвращает `tenant_id`
- ✅ `tenant_utils.py` — общий helper `load_restaurant` (используют co_invoices + co_writeoffs)
- ✅ `co_invoices.py` — полностью изолирован по `tenant_id`
- ✅ `co_writeoffs.py` — полностью изолирован по `tenant_id` (под-шаги А+Б+В)
- ⬜ `co_admin.py` — следующий (разведка → правки по под-шагам)
- ⬜ Суперадмин-роутер
- ⬜ Регистрация + онбординг
- ⬜ Биллинг

### Ключевые решения по мультитенантности

- **Паттерн фильтрации:** таблицы с `tenant_id` → `.filter(Model.tenant_id == user.tenant_id)`.
- **Транзитивные таблицы** (Invoice, WriteoffAct, Warehouse) → нет своей колонки, изоляция через
  `join(CoRestaurant).filter(CoRestaurant.tenant_id == user.tenant_id)`.
- **INSERT** в таблицы с `tenant_id` → всегда `tenant_id=user.tenant_id`.
- **Общий helper:** `backend/app/core/tenant_utils.py` → `load_restaurant(db, rid, user)`
  (грузит ресторан с tenant-фильтром, 404 если чужой/нет).
- **`_check_access`** во всех роутерах: сначала `load_restaurant` (tenant-гейт), потом проверка role.
- **`_user_restaurant_ids`** для admin: грузит рестораны тенанта из БД (НЕ возвращает `None`).
- **Таблицы БЕЗ `tenant_id`** (транзитив): Invoice, WriteoffAct, Warehouse, InvoiceItem, WriteoffItem.
- **Таблицы С `tenant_id`:** Restaurant, User, Supplier, Product, Account, WarehouseType,
  ProductGroup, Setting.

### 🔴 Железное правило

⚠️ `co_admin.py` — следующий файл на фильтрацию (~50 хендлеров).
Начинать **только с разведки** (read-only промт). Разбивать на под-шаги, как `co_writeoffs.py`.

---

## Карта файлов

**Backend** (`backend/app/`):
- `models/co_models.py` — все ORM-модели (схема `coffee_original`)
- `api/co_auth.py` — `/api/co/auth/...` (JWT)
- `api/co_admin.py` — `/api/co/admin/...` (CRUD + iiko sync)
- `api/co_invoices.py` — `/api/co/invoices/...` (OCR накладные)
- `api/co_writeoffs.py` — акты списания
- `core/security.py`, `core/database.py`, `core/config.py`
- `alembic/` — миграции (version_table в схеме `coffee_original`)

**Frontend** (`frontend/src/`): `api/coClient.ts`, `pages/co/CoLoginPage.tsx`,
`CoAdminPage.tsx`, `CoInvoicesPage.tsx`.

---

## Частые команды

```bash
# Бэкап БД вручную
/opt/reston/scripts/backup_host_db.sh

# Пересборка backend после правки .py
docker-compose -f docker-compose.prod.yml build backend
docker-compose -f docker-compose.prod.yml up -d --no-deps backend

# Alembic (из celery — там код смонтирован живьём)
docker exec reston-celery-1 alembic current

# Проверка прода
curl -I https://reston.kz
docker logs reston-backend-1 --tail 30
docker ps --filter name=reston
```

---

## Тестовые пользователи

- `admin@coffee.kz` / `admin123` — admin → `/co/admin`
- `karina@coffee.kz` / `1234` — user → `/co/invoices`
