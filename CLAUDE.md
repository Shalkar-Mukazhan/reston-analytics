# CLAUDE.md — RestOn / Coffee Original

Состояние на 2026-07-04. Проект обслуживает одного клиента — **Coffee Original (CO)**.
Старый код «Reston» вырезан рефакторингом (см. git `be89c9a`), осталась только CO-логика.
Идёт перевод на **мультитенантность (SaaS)** — см. раздел ниже. Alembic head: `0058`.

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

## ✅ Сделано (2026-07-04) — Акт сверки

Новая фича: сверка присланного поставщиком акта сверки взаиморасчётов (xls/xlsx/pdf)
с приходными накладными **напрямую из iiko** (без OLAP, без OCR/LLM — детерминированный
разбор файла). Мотивация: `co_invoices` (наша БД) отражает только то, что прогнали через
OCR в RestOn, а бухгалтеры часто вводят накладные прямо в iikoOffice — сверка с живым iiko
надёжнее.

- **`backend/app/services/reconciliation_parser.py`** — парсит xls (`xlrd`)/xlsx (`openpyxl`)/
  pdf (`pdfplumber`, `extract_tables()`). Формат акта — стандартная 1С-выгрузка: два зеркальных
  блока «Дата|Документ|Дебет|Кредит» (наша сторона и сторона поставщика), опознаются по
  заголовку (`_find_header_columns`), БИН и период — regex по полному тексту.
- **`backend/app/services/co_iiko.py`** → `fetch_incoming_invoices(restaurant, supplier_iiko_id, date_from, date_to)`
  — GET `/resto/api/documents/export/incomingInvoice?supplierId=...`, без OLAP.
- **`backend/app/api/co_reconciliation.py`** (`/api/co/reconciliation/...`):
  `POST /check` (сверка без сохранения), `POST /save`, `GET /` (список), `GET /{id}`, `DELETE /{id}`.
- **Таблица `co_reconciliation_acts`** — миграция `0058`, модель `CoReconciliationAct` в `co_models.py`.
  Тенант — транзитивно через `restaurant_id` (как `CoInvoice`/`CoWriteoffAct`, без своей колонки `tenant_id`).
- **`frontend/src/pages/co/CoReconciliationPage.tsx`** — маршрут `/reconciliation`, пункт «Акт сверки» в сайдбаре.
- **requirements.txt** — добавлены `xlrd==2.0.1`, `pdfplumber==0.11.4`.

### Ключевые решения по логике сверки

- **Кто есть кто в акте**: слева всегда поставщик (выставил акт), справа — мы. Определяется
  по БИН: сначала ищем поставщика по БИН **левой** колонки, и только потом — правой.
  ⚠️ **Не искать по обоим БИН сразу через `IN(...)`** — был баг: в справочнике поставщиков
  есть «мусорные» записи с БИН самого ресторана (см. «Известные проблемы данных» ниже),
  порядок в `IN(...)` непредсказуем и мог выбрать не того поставщика.
- **Дебет/Кредит с нашей стороны**: Кредит = накладная (наш долг растёт), Дебет = оплата
  (наш долг падает). Если наша колонка в файле пустая (обычное дело — заполняет только
  поставщик) — берём цифру с их стороны и переворачиваем Дебет/Кредит.
- **Период запроса к iiko** — берём по фактическим датам строк акта (± 2 дня допуск), а НЕ
  по шапке документа целиком: строки обычно начинают позже начала заявленного периода
  (то, что раньше — уже в сальдо на начало, попадание в OLAP/выгрузку даёт ложные "лишние").
- **Сопоставление накладных**: по сумме (±1 тенге) и дате (±2 дня — дата реализации у
  поставщика может отличаться от даты оприходования в iiko на 1 день).
  🔴 **Баг-ловушка**: `_days_apart(...) or 99` ломается для точного совпадения (diff=0 falsy
  в Python) — использовать `_dates_close()` с явной проверкой `is not None`.
- **Номер поставщика vs iiko**: внешний номер поставщика («10668») хранится в
  `incomingDocumentNumber`, а не в `documentNumber` (это внутренний номер iiko).

### ⚠️ Известные проблемы данных (найдены при тестировании, не исправлены)

- **Задвоение ресторана «Айтеке би»** — `id=20` (code `AYTEKE`) и `id=18` (code `AITEKE BI`)
  указывают на ОДИН и тот же `base_url` (`coffee-original-ayteke-bi.iiko.it`), оба `is_active=true`.
- **«Мусорные» поставщики с БИН ресторана** — минимум у CO Alem (БИН `020513600676`) в
  `suppliers` есть 6 записей-складов («Алем: Алем Бар/Кухня/Кондитерка/Хозка/Штучка/Основной
  склад») с тем же БИН. Похоже на `INTERNAL_SUPPLIER` (внутренний поставщик в iiko —
  служебный контрагент для межскладских перемещений), случайно попавший в справочник при
  синхронизации поставщиков в `co_admin.py`. Требует решения при работе над `co_admin.py`.
- **Ресторан «СО KUNAEVA»** — есть присланный акт сверки от него, но такого ресторана нет
  в `restaurants` вообще — нужно завести, если сверка по нему тоже нужна.

---

## 🔲 Осталось

- **A4 — чистка `requirements.txt`** (отдельная задача с пересборкой 3 образов):
  удалить `gspread`, `google-auth`, `reportlab`, `tenacity` (0 импортов).
  ⚠️ `openpyxl` теперь ИСПОЛЬЗУЕТСЯ (`reconciliation_parser.py`, парсинг xlsx) — из списка на
  удаление убрать. 🔴 `httpx` НЕ трогать — нужен `anthropic`. Заодно убрать осиротевшие
  импорты в `security.py` (`Depends`, `Session`, `get_db`, `OAuth2PasswordBearer`, `oauth2_scheme`).
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
- ✅ Суперадмин-роутер — `api/co_superadmin.py`, `/api/superadmin/tenants` (create/list/patch),
  защита через заголовок `X-Superadmin-Secret` (env `SUPERADMIN_SECRET`, настроен на проде).
  Проверено вживую 2026-07-04 — работает, в базе уже 3 тенанта (Coffee Original + 2 self-serve
  freelancer/trial). **Фронтенд-страницы нет** — только прямые запросы к API.
- ✅ Регистрация + онбординг — Google OAuth + onboarding flow (см. коммит), уже есть live-тенанты
  через самостоятельную регистрацию.
- ⬜ `co_admin.py` — следующий (разведка → правки по под-шагам)
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

## Бренд RestOn

### Цвета (использовать ВЕЗДЕ — в коде, компонентах, стилях)

| Токен Tailwind        | Hex       | Назначение                                          |
|-----------------------|-----------|-----------------------------------------------------|
| `brand-navy` / `brand-dark` | `#0F2D3D` | Primary Navy — заголовки, sidebar, структура        |
| `brand-green` / `brand-yellow` | `#0D9373` | Accent Green — кнопки, активный пункт меню, success |
| `brand-bg`            | `#F8F7F4` | Warm off-white — фон страниц                        |
| `brand-muted`         | `#64748b`  | Вторичный текст, подписи                            |
| `brand-border`        | `#E2E8F0` | Границы карточек и инпутов                          |
| `brand-red`           | `#EF4444` | Только ошибки (errors)                              |
| `brand-amber`         | `#F59E0B` | Только предупреждения (warnings/pending)            |

> **Жёлтый (`#FDB714`) — больше не используется.** `brand-yellow` теперь = `#0D9373` (green alias для обратной совместимости).

### SVG Бренд-файлы

**Хранятся в двух местах:**
- Исходники: `/opt/reston/brand/` (эталон)
- Frontend public: `/opt/reston/frontend/public/brand/` (используются в браузере)
- GitHub источник: `https://github.com/Shalkar-Mukazhan/new-reston/tree/main/brand`

**Файлы и правила использования:**

| Файл | Содержимое | Когда использовать |
|------|-----------|---------------------|
| `logo-dark.svg` | Белый R-иконка + белый "RestOn" | **Тёмный/navy фон** (sidebar, правая панель login) |
| `logo-light.svg` | Navy R-иконка + navy "RestOn" | **Светлый/белый фон** (login форма, страницы) |
| `icon-dark.svg` | Белая иконка R (без текста) | Маленький вариант на **тёмном** фоне |
| `icon-light.svg` | Navy иконка R (без текста) | Маленький вариант на **светлом** фоне |
| `wordmark-primary.svg` | "RestOn" текст navy + green "On" | Только текст, для светлых поверхностей |
| `wordmark-white.svg` | "RestOn" текст белый | Только текст, для тёмных поверхностей |
| `favicon.svg` | Квадратный R-иконка | Favicon браузера |

**Favicon PNG (конвертированы из SVG через rsvg-convert):**
- `/frontend/public/favicon-32.png` — 32×32 (вкладка браузера)
- `/frontend/public/apple-touch-icon.png` — 180×180 (iOS)
- `/frontend/public/favicon-192.png` — 192×192 (Android)

**Логотип не перерисовывать и не менять цвета!**

### Правила дизайна (для новых компонентов)

- **Стиль**: premium B2B SaaS, чистый, не Bootstrap-панель
- **Sidebar**: navy фон `#0F2D3D`, активный пункт = `bg-white/10` + `border-l-2 border-brand-green` + белый текст
- **Кнопки primary**: `bg-brand-green text-white` (зелёные, НЕ жёлтые)
- **Карточки**: `bg-white rounded-xl border border-brand-border shadow-sm` (класс `.card`)
- **Статус-chips**: badge-ok (зелёный), badge-warn (amber), badge-over (red), badge-muted (grey), badge-blue
- **Фон страниц**: `bg-brand-bg` (`#F8F7F4` warm off-white)
- **RestOn** — название платформы. **Coffee Original** — только workspace/клиент внутри системы.

---

## Карта файлов

**Backend** (`backend/app/`):
- `models/co_models.py` — все ORM-модели (схема `coffee_original`)
- `api/co_auth.py` — `/api/co/auth/...` (JWT)
- `api/co_admin.py` — `/api/co/admin/...` (CRUD + iiko sync)
- `api/co_invoices.py` — `/api/co/invoices/...` (OCR накладные)
- `api/co_writeoffs.py` — акты списания
- `api/co_superadmin.py` — `/api/superadmin/...` (управление тенантами, без UI)
- `api/co_reconciliation.py` — `/api/co/reconciliation/...` (акт сверки, см. раздел выше)
- `services/co_iiko.py` — iiko API хелперы (`fetch_olap`, `fetch_incoming_invoices`, `post_writeoff`)
- `services/reconciliation_parser.py` — детерминированный парсер актов сверки (xls/xlsx/pdf)
- `core/security.py`, `core/database.py`, `core/config.py`
- `alembic/` — миграции (version_table в схеме `coffee_original`)

**Frontend** (`frontend/src/`):
- `pages/co/CoLoginPage.tsx` — split-screen login (logo-light.svg слева, logo-dark.svg справа)
- `pages/co/CoLayout.tsx` — sidebar (navy, icon-dark.svg) + topbar (icon-light.svg)
- `pages/co/CoDashboardPage.tsx` — обзорный dashboard (KPI, Smart Upload, таблица)
- `pages/co/CoAdminPage.tsx` — CRUD: рестораны, склады, товары, поставщики, маппинг, пользователи
- `pages/co/CoInvoicesPage.tsx` — загрузка и обработка накладных (OCR)
- `pages/co/CoWriteoffPage.tsx` — акты списания
- `pages/co/CoReconciliationPage.tsx` — акт сверки (загрузка файла, сверка с iiko, история)
- `api/coClient.ts` — axios клиент для `/api/co/...`

**Маршруты frontend:**
- `/login` → CoLoginPage
- `/dashboard` → CoDashboardPage (admin после логина)
- `/invoices` → CoInvoicesPage (user после логина)
- `/writeoffs` → CoWriteoffPage
- `/reconciliation` → CoReconciliationPage (акт сверки)
- `/admin?tab=<tab>` → CoAdminPage (tabs: restaurants, warehouses, products, suppliers, mapping, users, containers)

**Бренд-файлы:**
- `/opt/reston/brand/` — эталонные SVG/PNG
- `/opt/reston/frontend/public/brand/` — копия для браузера (обновлять синхронно!)

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

## Частые команды (дополнение)

```bash
# Синхронизировать бренд-файлы (GitHub → сервер → frontend/public)
BASE="https://raw.githubusercontent.com/Shalkar-Mukazhan/new-reston/main/brand"
for f in favicon.svg icon-dark.svg icon-light.svg logo-dark.svg logo-light.svg wordmark-primary.svg wordmark-white.svg; do
  curl -sL "$BASE/$f" -o "/opt/reston/brand/$f"
  cp "/opt/reston/brand/$f" "/opt/reston/frontend/public/brand/$f"
done
# После обновления favicon.svg — перегенерировать PNG:
rsvg-convert -w 32 -h 32 /opt/reston/brand/favicon.svg -o /opt/reston/frontend/public/favicon-32.png
rsvg-convert -w 180 -h 180 /opt/reston/brand/favicon.svg -o /opt/reston/frontend/public/apple-touch-icon.png

# Перезапуск frontend (код живой через mount, restart достаточно)
docker restart reston-frontend-1
```

---

## Тестовые пользователи

- `admin@coffee.kz` / `admin123` — admin → `/dashboard` (после логина)
- `karina@coffee.kz` / `1234` — user → `/invoices` (после логина)
