# Coffee Original — Система управления складом

## Обзор

Отдельный клиент `coffee_original` на той же инфраструктуре что и reston.
- Один бэкенд (FastAPI), одна БД (PostgreSQL)
- Данные изолированы в отдельной PostgreSQL схеме `coffee_original`
- Отдельная авторизация (JWT с `tenant: "co"`)

---

## Архитектура

### База данных
```
PostgreSQL DB: wastecontrol
├── public (схема)          ← reston (существующий клиент)
└── coffee_original (схема) ← новый клиент
```

### Миграции
| Файл | Что делает |
|------|------------|
| `0037_coffee_original_schema.py` | Создаёт схему и все базовые таблицы |
| `0038_co_add_iiko_ids.py` | Добавляет `iiko_id` в suppliers, unique на products |
| `0039_co_mapping_add_code.py` | `supplier_product_code` в product_mapping |
| `0040_co_containers.py` | Таблица `product_containers` + `container_id` в mapping |

---

## Таблицы схемы `coffee_original`

### `restaurants`
Рестораны клиента — доступ к iiko серверу.
```
id, code, name, base_url, iiko_login, iiko_password_hash, is_active
```
- `base_url` — URL iiko сервера (например `https://coffee-original-tole-bi.iiko.it`)
- `iiko_password_hash` — SHA1 хэш пароля iiko
- iiko сервер: `coffee-original-tole-bi.iiko.it` (HTTPS!)

### `restaurant_warehouses`
Склады внутри ресторана (бар, кухня, кондитерка и т.д.)
```
id, restaurant_id, name, iiko_store_id, is_active
```
- `iiko_store_id` — UUID склада в iiko (нужен для отправки накладных)
- Заполняется через кнопку "Синхр. склады"

### `users`
Пользователи CO системы (отдельные от reston!).
```
id, email, name, password_hash, role, is_active
```
- `role`: `admin` | `user`
- Логин по email (в отличие от reston где логин по username)

Текущие пользователи:
- `admin@coffee.kz` / `admin123` — роль admin
- `karina@coffee.kz` / `1234` — роль user (только накладные)

### `user_restaurants`
Many-to-many: пользователь ↔ ресторан.
```
user_id, restaurant_id
```

### `suppliers`
Поставщики. Синхронизируются из iiko `/resto/api/suppliers`.
```
id, iiko_id, name, bin, contact, is_active
```
- `iiko_id` — UUID поставщика в iiko (нужен для отправки накладных)
- При отправке накладной в iiko нужен ВНЕШНИЙ поставщик, не внутренний склад!

### `products`
Товары/номенклатура из iiko.
```
id, iiko_article_id, name, unit, is_active
```
- `iiko_article_id` — UUID товара в iiko
- Синхронизируется из `/resto/api/v2/entities/products/list`
- Всего ~906 товаров

### `product_containers`
Кейсовки/упаковки товаров (из iiko).
```
id, product_id, iiko_container_id, name, count
```
- `iiko_container_id` — UUID контейнера в iiko
- `count` — кол-во единиц в упаковке
- Синхронизируются АВТОМАТИЧЕСКИ вместе с товарами (поле `containers` в ответе iiko)

### `product_mapping`
Маппинг: название у поставщика → товар в iiko.
```
id, supplier_id, product_id, supplier_product_name, supplier_product_code, container_id
```
- `supplier_product_code` — артикул поставщика (для поиска при сканировании)
- `container_id` — ссылка на кейсовку (если товар продаётся в упаковках)
- При сохранении накладной: автопоиск по коду → по названию → нечёткий поиск

### `invoices`
Накладные (приходные).
```
id, restaurant_id, warehouse_id, supplier_id, invoice_date, status, created_by, created_at
```
- `status`: `draft` | `sent` | `error`
- `warehouse_id` — склад НАЗНАЧЕНИЯ (Толе би Кухня, Байтурсынова Бар и т.д.)

### `invoice_items`
Строки накладной.
```
id, invoice_id, product_id, supplier_product_name, qty, price
```
- `product_id` — привязка к iiko товару (через маппинг или нечёткий поиск)

---

## Бэкенд файлы

### `app/models/co_models.py`
SQLAlchemy модели для всех таблиц схемы `coffee_original`.
Классы: `CoRestaurant`, `CoWarehouse`, `CoUser`, `CoUserRestaurant`, `CoSupplier`, `CoProduct`, `CoProductContainer`, `CoProductMapping`, `CoInvoice`, `CoInvoiceItem`

### `app/api/co_auth.py`
Авторизация CO (`/api/co/auth/...`).
- `POST /login` — логин по email/password, возвращает JWT с `tenant: "co"`
- `POST /refresh` — обновление токена
- `GET /me` — текущий пользователь
- `POST /bootstrap` — создать первого admin (требует `CO_BOOTSTRAP_SECRET`)
- Dependency: `get_current_co_user`, `require_co_admin`

### `app/api/co_admin.py`
Административные функции (`/api/co/admin/...`).

**Рестораны:** CRUD + 3 кнопки синхронизации iiko:
- `POST /restaurants/{id}/sync/warehouses` → `/resto/api/corporation/stores` (XML)
- `POST /restaurants/{id}/sync/products` → `/resto/api/v2/entities/products/list` (JSON) + автосохранение контейнеров
- `POST /restaurants/{id}/sync/suppliers` → `/resto/api/suppliers` (XML)

**Остальные:** CRUD для складов, поставщиков, товаров, маппинга, контейнеров, пользователей.

Helper `_iiko_session(restaurant)` — получает session key, обрабатывает ошибки подключения.
Helper `_normalize_url(url)` — добавляет `https://` если нет схемы.

### `app/api/co_invoices.py`
Накладные OCR (`/api/co/invoices/...`) — аналог invoices2 для CO.
- `POST /ocr-parse` — распознать фото/PDF через Claude Vision (без сохранения)
- `POST /ocr-confirm` — сохранить после проверки (автомаппинг: маппинг → нечёткий поиск)
- `GET /` — список накладных
- `GET /{id}/items` — позиции накладной
- `POST /{id}/post-to-iiko` — отправить в iiko

**Логика автомаппинга при сохранении:**
1. Ищет по коду поставщика в `product_mapping`
2. Ищет по названию в `product_mapping`
3. Нечёткий поиск по словам (>3 символа) в `products.name`

**Логика отправки в iiko:**
- XML формат как у reston invoices2
- Если у маппинга есть `container_id`: `amount = qty × count`, `price = price ÷ count`, добавляет `<containerId>`
- Требует: поставщик с `iiko_id`, склад с `iiko_store_id`

---

## Фронтенд файлы

### `src/api/coClient.ts`
Отдельный axios инстанс для CO.
- `baseURL: '/api/co'`
- Токены: `co_access_token`, `co_refresh_token` в localStorage
- 401 interceptor НЕ срабатывает на `/auth/login` (чтобы не ломать логин)

### `src/pages/co/CoLoginPage.tsx`
Страница входа CO. URL: `/co/login`

### `src/pages/co/CoAdminPage.tsx`
Административная панель. URL: `/co/admin`
Табы: Рестораны | Склады | Товары | Поставщики | Маппинг | Кейсовки | Пользователи

### `src/pages/co/CoInvoicesPage.tsx`
Страница накладных. URL: `/co/invoices`
Аналог `Invoices2Page` для reston + выбор склада.

---

## Авторизация и роутинг

### Единый логин (`/login`)
Один логин для всех — сначала пробует reston, если не нашёл — пробует CO.
- reston юзер → `/dashboard`
- CO admin → `/co/admin`
- CO user → `/co/invoices`

Исправление в `client.ts`: interceptor не редиректит при 401 на `/auth/login`.

### CO JWT
`{ sub: user_id, tenant: "co", exp: ... }`
Отличается от reston токена наличием `tenant: "co"`.

---

## Сценарий использования

### Первоначальная настройка (admin):
1. `/co/admin` → Рестораны → Добавить ресторан (URL, логин, SHA1 пароль)
2. Рестораны → "Синхр. склады" — подтягивает склады из iiko
3. Рестораны → "Синхр. поставщиков" — подтягивает поставщиков
4. Рестораны → "Синхр. товары" — подтягивает номенклатуру + кейсовки
5. Маппинг → выбрать поставщика → добавить маппинги (код + название → iiko товар + кейсовка)

### Работа с накладными (Karina):
1. `/co/invoices` → выбрать ресторан + склад → загрузить фото/PDF
2. Claude распознаёт накладную
3. Проверить/исправить данные
4. "Сохранить накладную" — автоматически привязывает товары через маппинг
5. "В iiko" → указать дату прихода → отправить

### SHA1 пароль для iiko:
```bash
echo -n "ВАШ_ПАРОЛЬ" | sha1sum
```

---

## iiko API особенности

- Сервер: `https://coffee-original-tole-bi.iiko.it` (только HTTPS!)
- Авторизация: `GET /resto/api/auth?login=X&pass=SHA1_HASH`
- Склады: `GET /resto/api/corporation/stores` → XML, тип `STORE`
- Товары: `GET /resto/api/v2/entities/products/list` → JSON, поле `containers`
- Поставщики: `GET /resto/api/suppliers` → XML, тег `<employee>`
- Накладная: `POST /resto/api/documents/import/incomingInvoice` → XML

**XML накладной:**
```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<document>
  <items>
    <item>
      <num>1</num>
      <product>PRODUCT_UUID</product>
      <store>STORE_UUID</store>
      <amount>5.0000</amount>
      <price>770.0000</price>
      <sum>3850.00</sum>
      <containerId>CONTAINER_UUID</containerId>  <!-- если кейсовка -->
    </item>
  </items>
  <dateIncoming>23.04.2026</dateIncoming>
  <useDefaultDocumentTime>true</useDefaultDocumentTime>
  <invoice>DOC_NUMBER</invoice>
  <defaultStore>STORE_UUID</defaultStore>
  <supplier>SUPPLIER_IIKO_UUID</supplier>
  <status>NEW</status>
</document>
```

**Частые ошибки iiko:**
- `401` → неверный SHA1 пароль
- `Document department is not unique` → неверный UUID склада или логин без доступа
- `Нет позиций с iiko маппингом` → нет маппинга И нечёткий поиск не нашёл товар
