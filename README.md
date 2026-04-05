# Reston Analytics — Полная документация

> Система аналитики и контроля ресторанов сети I'M  
> **Статус:** Разработка завершена, готово к деплою на сервер

---

## Содержание

1. [Что это за проект](#1-что-это-за-проект)
2. [Технологии](#2-технологии)
3. [Архитектура системы](#3-архитектура-системы)
4. [Разделы и логика](#4-разделы-и-логика)
5. [Текущий статус — что сделано](#5-текущий-статус--что-сделано)
6. [Структура файлов](#6-структура-файлов)
7. [Файлы которые нужно скопировать вручную](#7-файлы-которые-нужно-скопировать-вручную)
8. [Локальная разработка](#8-локальная-разработка)
9. [Деплой на сервер — пошагово](#9-деплой-на-сервер--пошагово)
10. [Требования к серверу](#10-требования-к-серверу)
11. [Подключение домена и SSL](#11-подключение-домена-и-ssl)
12. [База данных — миграции](#12-база-данных--миграции)
13. [Как обновить после деплоя](#13-как-обновить-после-деплоя)
14. [Telegram алерты — настройка](#14-telegram-алерты--настройка)
15. [Часто встречающиеся проблемы](#15-часто-встречающиеся-проблемы)
16. [Анализ проблем и решений](#16-анализ-проблем-и-решений)

---

## 1. Что это за проект

**Reston Analytics** — веб-платформа для сети ресторанов I'M (27 ресторанов в Казахстане).

**Заменяет:** Desktop приложение WasteControl (Python/CustomTkinter) которое работало только на Windows.

**Пользователи:**
- `store` — менеджер одного ресторана (видит только свои данные)
- `co` — центральный офис (видит все рестораны)
- `admin` — полный доступ + администрирование

**Данные берутся из:** IIKO — у каждого ресторана свой сервер в облаке iiko.it  
Пример: `https://im-02009-adk.iiko.it`, `https://im-maxima-02005.iiko.it`

---

## 2. Технологии

| Слой | Технология |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy |
| База данных | PostgreSQL 16 |
| Кэш / очереди | Redis 7 |
| Фоновые задачи | Celery + Celery Beat |
| Frontend | React 18, TypeScript, Tailwind CSS, Recharts |
| Сборка | Vite |
| Контейнеры | Docker, Docker Compose |
| Обратный прокси | Nginx |
| Google Sheets | gspread + google-auth (сервисный аккаунт) |

---

## 3. Архитектура системы

```
Браузер пользователя
        │
        ▼
    Nginx :80/:443
    ┌─────┴──────┐
    │            │
/api/*       всё остальное
    │            │
 Backend      Frontend
 FastAPI      React (статика)
    │
    ├── PostgreSQL (данные, сессии, планы)
    ├── Redis (кэш IIKO ответов, очереди Celery)
    ├── Celery Worker (фоновые задачи)
    └── Celery Beat (расписание)
         │
         ├── 03:00 → синк аналитики из IIKO
         └── каждый час → чек-лист → Google Sheets

Backend → IIKO серверы (отдельный для каждого ресторана)
Backend → Google Sheets (сервисный аккаунт sheets-bot)
```

---

## 4. Разделы и логика

### Дашборд
- KPI плитки: выручка, GC, средний чек, списания (из нашей БД `waste_metrics`)
- Почасовые продажи текущего дня → IIKO OLAP в реальном времени
- Бизнес-день: 07:00→23:00→00:00→03:00 (не календарный)

### Отчёты
- Генерация отчётов по списаниям за период (неделя/месяц)
- Данные из IIKO: writeoff + sales + revenue_net пресеты
- Экспорт в Excel
- Метрики нормы списания по группам товаров

### Аналитика
- Исторические тренды продаж по месяцам
- Ночная синхронизация в 03:00 (Celery Beat) → `sales_daily_facts`

### Планирование
- Месячная таблица: GC план, продажи план, средний чек план
- Авто-планирование: взвешенное среднее 8 аналогичных дней из истории IIKO
- Директор может редактировать вручную
- Выбор месяца: -3/+3 от текущего
- Планы автоматически уходят в Google Sheets чек-листа (колонка "План")

### Чек-лист
- Каждый ресторан → своя Google Таблица
- Менеджер утром нажимает **"Начать новый день"**:
  - Очищает таблицу
  - Записывает план (из нашей БД или из истории IIKO)
  - Разбивка по каналам (DT, Kiosk, Café, DLV) из исторических пропорций
  - Включает почасовую синхронизацию
- Каждый час: факт из IIKO → Google Sheets (только если день начат)
- Кнопка "Скачать PDF" → экспорт из Google Sheets
- Пауза 30 сек между ресторанами при "Начать день (все)" для защиты IIKO

### Администрирование
- Управление пользователями (роли, привязка к ресторанам)
- Настройка ресторанов: IIKO URL, логин, пресеты OLAP, Google Sheet URL, час начала дня
- Проверка подключения к IIKO

---

## 5. Текущий статус — что сделано

### Полностью готово
- Авторизация JWT (access + refresh токены)
- Все 6 разделов (Дашборд, Отчёты, Аналитика, Планирование, Чек-лист, Админ)
- Celery Beat: ночной синк аналитики (03:00) + почасовой чек-лист синк
- Google Sheets интеграция (сервисный аккаунт sheets-bot)
- Кэш IIKO ответов в Redis (1 час)
- Кэш IIKO сессий в PostgreSQL (1 час, авто-обновление)
- Production Docker Compose (PostgreSQL + Nginx внутри)
- Бренд: Reston Analytics, логотипы forwhite.png/forblack.png
- Страница "О системе"

### Настроено локально (нужно перенести на сервер)
- PostgreSQL с данными ресторанов (27 ресторанов, пресеты, пользователи)
- Google сервисный аккаунт credentials
- Google Sheet URL для Maxima и ADK

### Не реализовано (отложено)
- Раздел "Продажи" (планирование продаж — отдельный проект Rest)
- Telegram уведомления
- Sentry мониторинг ошибок

---

## 6. Структура файлов

```
reston-analytics/
├── docker-compose.yml          ← локальная разработка
├── docker-compose.prod.yml     ← ПРОДАКШН (используй этот на сервере)
├── .env.example                ← шаблон переменных окружения
├── .gitignore                  ← .env и credentials НЕ в git
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── google_credentials.json ← НЕ в git, копируешь вручную!
│   ├── alembic/
│   │   └── versions/           ← все миграции БД (0001–0026)
│   └── app/
│       ├── api/                ← эндпоинты FastAPI
│       │   ├── auth.py
│       │   ├── dashboard.py
│       │   ├── reports.py
│       │   ├── analytics.py
│       │   ├── planning.py
│       │   ├── checklist.py    ← start-day, status, Google Sheets
│       │   ├── invoices.py
│       │   └── admin.py
│       ├── models/             ← SQLAlchemy модели
│       ├── services/
│       │   └── iiko.py         ← все запросы к IIKO + кэш
│       └── tasks/
│           ├── celery_app.py   ← расписание Celery Beat
│           ├── checklist_tasks.py ← синк с Google Sheets
│           └── report_tasks.py    ← ночная аналитика
│
├── frontend/
│   ├── Dockerfile              ← dev (npm run dev)
│   ├── Dockerfile.prod         ← prod (собирает статику)
│   ├── nginx.frontend.conf     ← SPA роутинг
│   └── src/
│       ├── pages/              ← все страницы
│       └── components/         ← Layout, навигация
│
└── nginx/
    └── nginx.conf              ← обратный прокси
```

---

## 7. Файлы которые нужно скопировать вручную

Эти файлы **не в git** (секреты). Нужно скопировать на сервер вручную.

### `.env` — главный файл конфигурации

Создай на сервере: `nano /opt/reston-analytics/.env`

```env
# База данных
POSTGRES_DB=wastecontrol
POSTGRES_USER=wastecontrol_user
POSTGRES_PASSWORD=ПРИДУМАЙ_СИЛЬНЫЙ_ПАРОЛЬ
DATABASE_URL=postgresql://wastecontrol_user:ПРИДУМАЙ_СИЛЬНЫЙ_ПАРОЛЬ@postgres:5432/wastecontrol

# JWT (минимум 32 символа, можно сгенерировать: openssl rand -hex 32)
SECRET_KEY=СГЕНЕРИРУЙ_СЛУЧАЙНЫЙ_КЛЮЧ
ACCESS_TOKEN_EXPIRE_MINUTES=480
REFRESH_TOKEN_EXPIRE_DAYS=30

# Redis
REDIS_URL=redis://redis:6379/0

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# Sentry (опционально)
SENTRY_DSN=
```

### `backend/google_credentials.json` — Google сервисный аккаунт

Файл уже есть локально: `/Users/shalkar/Desktop/wastecontrol-web/backend/google_credentials.json`

Скопировать на сервер:
```bash
scp /Users/shalkar/Desktop/wastecontrol-web/backend/google_credentials.json \
    user@SERVER_IP:/opt/reston-analytics/backend/google_credentials.json
```

Это credentials сервисного аккаунта `sheets-bot@shalkar-project.iam.gserviceaccount.com`  
Он пишет данные в Google Sheets ресторанов.

---

## 8. Локальная разработка

```bash
# Клонировать
git clone https://github.com/Shalkar-Mukazhan/reston-analytics.git
cd reston-analytics

# Создать .env (заполни DATABASE_URL с host.docker.internal)
cp .env.example .env

# Запустить
docker compose up -d --build

# Применить миграции
docker compose exec backend alembic upgrade head

# Открыть
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000/docs
```

---

## 9. Деплой на сервер — пошагово

### Шаг 1: Установить Docker на сервере

```bash
# Подключиться к серверу
ssh root@SERVER_IP

# Установить Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker

# Установить docker compose plugin
apt-get install docker-compose-plugin -y
```

### Шаг 2: Клонировать репозиторий

```bash
mkdir -p /opt/reston-analytics
cd /opt/reston-analytics
git clone https://github.com/Shalkar-Mukazhan/reston-analytics.git .
```

### Шаг 3: Создать .env на сервере

```bash
cp .env.example .env
nano .env
# Заполни все значения (пароли, SECRET_KEY)
```

Сгенерировать SECRET_KEY:
```bash
openssl rand -hex 32
```

### Шаг 4: Скопировать google_credentials.json

**На локальном Mac:**
```bash
scp /Users/shalkar/Desktop/wastecontrol-web/backend/google_credentials.json \
    root@SERVER_IP:/opt/reston-analytics/backend/google_credentials.json
```

### Шаг 5: Перенести данные БД (если нужны данные с локалки)

**На локальном Mac:**
```bash
# Экспорт локальной БД
docker compose exec postgres pg_dump -U wastecontrol_user wastecontrol > backup.sql

# Копировать на сервер
scp backup.sql root@SERVER_IP:/opt/reston-analytics/backup.sql
```

**На сервере:**
```bash
# Сначала запустить только postgres
docker compose -f docker-compose.prod.yml up -d postgres
sleep 10

# Импортировать дамп
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U wastecontrol_user wastecontrol < backup.sql
```

### Шаг 6: Собрать и запустить

```bash
cd /opt/reston-analytics
docker compose -f docker-compose.prod.yml up -d --build
```

Проверить что все контейнеры запустились:
```bash
docker compose -f docker-compose.prod.yml ps
```

Должно быть 6 контейнеров: postgres, redis, backend, celery, celery-beat, frontend, nginx

### Шаг 7: Применить миграции (если БД новая)

```bash
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Шаг 8: Создать первого admin пользователя

```bash
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.database import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash
db = SessionLocal()
u = User(username='admin', password_hash=get_password_hash('ТВОЙ_ПАРОЛЬ'), role='admin')
db.add(u)
db.commit()
print('Admin создан')
"
```

### Шаг 9: Проверить

```bash
# Логи backend
docker compose -f docker-compose.prod.yml logs backend --tail=20

# Логи celery
docker compose -f docker-compose.prod.yml logs celery --tail=20

# Открыть в браузере
http://SERVER_IP
```

---

## 10. Требования к серверу

### Минимальные (для старта)
| Параметр | Минимум | Рекомендуется |
|---|---|---|
| CPU | 2 ядра | 4 ядра |
| RAM | 2 GB | 4 GB |
| Диск | 20 GB SSD | 40 GB SSD |
| ОС | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |
| Сеть | 100 Mbps | 1 Gbps |

### Где купить (Казахстан)
- **ps.kz** — казахстанские серверы, оплата тенге
- **beget.com** — российский хостинг, VPS от 500 руб
- **DigitalOcean** — международный, от $6/мес (Droplet)
- **Hetzner** — европейский, дешевле всех, от €4/мес

### Рекомендация
Для 27 ресторанов: **VPS с 2 CPU / 4 GB RAM / 40 GB SSD**  
Примерная стоимость: $10-15/месяц

---

## 11. Подключение домена и SSL

### Шаг 1: Купить домен
- Любой регистратор: ps.kz, nic.kz, namecheap.com
- Пример: `reston.im-almaty.kz`

### Шаг 2: DNS настройки
В панели управления доменом добавь A-запись:
```
Тип: A
Имя: @  (или reston)
Значение: IP_АДРЕС_СЕРВЕРА
TTL: 3600
```

### Шаг 3: Установить Certbot (SSL бесплатно)

```bash
# На сервере
apt-get install certbot -y

# Остановить nginx на время получения сертификата
docker compose -f docker-compose.prod.yml stop nginx

# Получить сертификат
certbot certonly --standalone -d reston.im-almaty.kz

# Сертификаты будут в:
# /etc/letsencrypt/live/reston.im-almaty.kz/fullchain.pem
# /etc/letsencrypt/live/reston.im-almaty.kz/privkey.pem
```

### Шаг 4: Обновить nginx.conf для HTTPS

```nginx
server {
    listen 80;
    server_name reston.im-almaty.kz;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name reston.im-almaty.kz;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;

    client_max_body_size 50M;

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://frontend:80;
        proxy_set_header Host $host;
    }
}
```

### Шаг 5: Смонтировать сертификаты в nginx

В `docker-compose.prod.yml` volumes у nginx:
```yaml
volumes:
  - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
  - /etc/letsencrypt/live/reston.im-almaty.kz/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
  - /etc/letsencrypt/live/reston.im-almaty.kz/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
```

### Шаг 6: Авто-обновление SSL (раз в 90 дней)

```bash
# Добавить в crontab
crontab -e

# Добавить строку:
0 3 * * * certbot renew --quiet && docker compose -f /opt/reston-analytics/docker-compose.prod.yml restart nginx
```

---

## 12. База данных — миграции

### Новый сервер (с нуля)
```bash
# Создаёт все таблицы по порядку (0001 → 0026)
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

### Перенос данных с локалки

```bash
# 1. На Mac — экспорт
cd /Users/shalkar/Desktop/wastecontrol-web
docker compose exec postgres pg_dump \
    -U wastecontrol_user wastecontrol \
    --no-owner --no-acl > backup_$(date +%Y%m%d).sql

# 2. Копируем на сервер
scp backup_20260406.sql root@SERVER_IP:/opt/reston-analytics/

# 3. На сервере — импорт
docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U wastecontrol_user wastecontrol < backup_20260406.sql
```

### Добавить новую миграцию (будущие изменения)
```bash
# Локально создать файл миграции
# Файл: backend/alembic/versions/0027_название.py

# На сервере применить
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 13. Как обновить после деплоя

Когда внёс изменения в код и запушил на GitHub:

```bash
# На сервере
cd /opt/reston-analytics

# Получить новый код
git pull origin main

# Пересобрать и перезапустить
docker compose -f docker-compose.prod.yml up -d --build

# Если были новые миграции
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 14. Часто встречающиеся проблемы

### Backend не стартует
```bash
docker compose -f docker-compose.prod.yml logs backend
# Скорее всего: нет .env или неверный DATABASE_URL
```

### Celery не видит задачи
```bash
docker compose -f docker-compose.prod.yml logs celery
# Скорее всего: Redis недоступен
```

### Google Sheets не работает
```bash
# Проверить что файл на месте
ls -la backend/google_credentials.json

# Проверить в celery
docker compose -f docker-compose.prod.yml exec celery python -c "
from app.tasks.checklist_tasks import _sheets_client
print(_sheets_client())
"
```

### IIKO возвращает 401
```bash
# Сбросить кэш сессий
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.database import SessionLocal
from app.models.report import IikoSession
db = SessionLocal()
db.query(IikoSession).delete()
db.commit()
print('Сессии очищены')
"
```

### Фронтенд показывает старую версию
```bash
# Пересобрать образ фронтенда
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

---

## 14. Telegram алерты — настройка

Алерты приходят в Telegram когда что-то идёт не так (или всё хорошо).

### Где находится .env локально
```
/Users/shalkar/Desktop/wastecontrol-web/.env
```
Этот файл не в GitHub — там пароли и ключи. На сервере создаётся вручную.

### Шаг 1: Создать бота
1. Открой Telegram → найди `@BotFather`
2. Напиши `/newbot`
3. Придумай имя: `Reston Analytics`
4. Получишь токен: `7123456789:AAF...` → это `TELEGRAM_BOT_TOKEN`
5. Напиши боту `/start` чтобы активировать

### Шаг 2: Узнать свой Chat ID
1. Найди `@userinfobot` в Telegram
2. Напиши ему что угодно
3. Он ответит твой ID: `123456789` → это `TELEGRAM_CHAT_ID`

### Шаг 3: Вставить в .env
```env
TELEGRAM_BOT_TOKEN=7123456789:AAF...
TELEGRAM_CHAT_ID=123456789
```

### Что приходит в Telegram
| Событие | Тип |
|---|---|
| Менеджер нажал "Начать день" | ✅ Успех |
| Ошибка синхронизации чек-листа | 🔴 Ошибка |
| Ночной синк аналитики запущен | ✅ Успех |
| Ошибка ночного синка | 🔴 Ошибка |

---

## 15. Часто встречающиеся проблемы

### Backend не стартует
```bash
docker compose -f docker-compose.prod.yml logs backend
# Скорее всего: нет .env или неверный DATABASE_URL
```

### Celery не видит задачи
```bash
docker compose -f docker-compose.prod.yml logs celery
# Скорее всего: Redis недоступен
```

### Google Sheets не работает
```bash
# Проверить что файл на месте
ls -la backend/google_credentials.json

# Проверить авторизацию
docker compose -f docker-compose.prod.yml exec celery python -c "
from app.tasks.checklist_tasks import _sheets_client
print(_sheets_client())
"
```

### IIKO возвращает 401
```bash
# Сбросить кэш сессий
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.database import SessionLocal
from app.models.report import IikoSession
db = SessionLocal()
db.query(IikoSession).delete()
db.commit()
print('Сессии очищены')
"
```

### Фронтенд показывает старую версию
```bash
docker compose -f docker-compose.prod.yml build frontend
docker compose -f docker-compose.prod.yml up -d frontend
```

### Чек-лист не обновляется
```bash
# Проверить запущен ли Celery Beat
docker compose -f docker-compose.prod.yml logs celery-beat --tail=20

# Проверить нажата ли кнопка "Начать день" сегодня
docker compose -f docker-compose.prod.yml exec backend python -c "
from app.core.database import SessionLocal
from app.models.restaurant import Restaurant
from datetime import date
db = SessionLocal()
today = date.today()
for r in db.query(Restaurant).filter(Restaurant.google_sheet_url != None).all():
    print(r.name, '→', r.last_checklist_reset_date, '| сегодня:', r.last_checklist_reset_date == today)
db.close()
"
```

---

## 16. Анализ проблем и решений

Все проблемы которые возникли в процессе разработки и как они были решены.

### 🔴 GOOGLE_SERVICE_ACCOUNT_JSON не грузился в Docker
**Проблема:** Docker Compose env_file не парсит JSON со спецсимволами. Переменная была пустой внутри контейнера.  
**Решение:** Вместо env var создали файл `backend/google_credentials.json` — он монтируется через volume `./backend:/app` автоматически. Код читает файл напрямую, env var — запасной вариант.

### 🔴 IIKO возвращал 409 на почасовом дашборде
**Проблема:** Пресет "Aim with hour" имеет тип DATE — нельзя указывать время в запросе. Попытка сделать `T20:00:00` → `T+1 T10:00:00` для бизнес-дня вызывала ошибку.  
**Решение:** Оставили стандартный диапазон `T00:00:00` → `T+1 T00:00:00`. IIKO сам фильтрует по OpenDate.Typed (бизнес-дата). Добавили только сортировку часов 7→23→0→6 на нашей стороне.

### 🔴 Процент каналов (киоск, DT) не попадал в Google Sheets
**Проблема:** При использовании плана из нашей БД устанавливали `kiosk_gc=0, dt_gc=0` — нет данных по каналам в нашей таблице планов.  
**Решение:** Пресет `sales` не имеет `RestorauntGroup` — канальные данные есть только в "Aim with hour". Сделали `_daily_from_hourly()` — суммируем почасовые данные в дневные. Получаем реальные пропорции каналов из истории, применяем к плановому GC.

### 🔴 Двойной /api/ префикс (404 на checklist endpoints)
**Проблема:** Frontend api клиент имеет `baseURL: '/api'`. Запросы `/api/checklist/...` превращались в `/api/api/checklist/...`.  
**Решение:** Убрали `/api` префикс из запросов в ChecklistPage — стало `/checklist/status`, `/checklist/start-day`.

### 🟡 Пароль admin неизвестен при первом запуске
**Проблема:** Пользователь `aruzhan` с ролью admin имел неизвестный пароль — не `admin123`.  
**Решение:** Сбросили пароль напрямую через bcrypt в контейнере postgres.

### 🟡 Celery Beat не было в docker-compose
**Проблема:** Чек-лист синхронизация через GitHub Actions (iiko_sync.py) — внешняя зависимость, нет контроля.  
**Решение:** Добавили сервис `celery-beat` в docker-compose. Перенесли всю логику iiko_sync.py в `checklist_tasks.py` на нашем сервере. GitHub Actions можно отключить.

### 🟡 Все рестораны синхронизировались в одну Google таблицу
**Проблема:** У ADK и Maxima был одинаковый `google_sheet_url` в БД — тестовый.  
**Решение:** Каждый ресторан должен иметь свою Google таблицу. URL настраивается в Админ → Рестораны. Инструкция: создать таблицу, поделиться с `sheets-bot@shalkar-project.iam.gserviceaccount.com`.

### 🟡 Автоматический сброс в 07:00 неудобен
**Проблема:** Если менеджер не пришёл в 07:00 — таблица очищена, план записан, но факт не тянется пока Celery не запустится в 08:00. Нет контроля.  
**Решение:** Убрали автоматический сброс. Добавили кнопку "Начать новый день" — менеджер сам нажимает когда приходит. Hourly sync работает только если сегодня нажата кнопка.

### 🟢 Нагрузка на IIKO при 27 ресторанах
**Проблема:** Все рестораны одновременно = перегрузка IIKO.  
**Решение 1:** Hourly sync — пауза 3 сек между ресторанами (27 рест = 80 сек).  
**Решение 2:** Кнопка "Начать день" — задержка 30 сек между Celery задачами (27 рест = 13 мин).  
**Плюс:** У каждого ресторана свой IIKO сервер (im-02009-adk.iiko.it и т.д.) — нагрузка распределена.

### 🟢 .DS_Store и celerybeat-schedule попали в git
**Проблема:** Системные файлы macOS и бинарный файл Celery в репозитории.  
**Решение:** Добавили в .gitignore, удалили из tracking через `git rm --cached`.

---

## Контакты и поддержка

- GitHub: https://github.com/Shalkar-Mukazhan/reston-analytics
- Google сервисный аккаунт: `sheets-bot@shalkar-project.iam.gserviceaccount.com`

---

*Документация актуальна на апрель 2026*
