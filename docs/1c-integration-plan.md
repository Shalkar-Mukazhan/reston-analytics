# Интеграция накладных от 1С (и других поставщиков)

## Проблема
Текущий парсер накладных (`invoice_parser.py`) жёстко заточен под ABL Excel формат:
- Требует листы `HEADER` и `DETAILS`
- Ищет колонку `Subsys` (ABL артикул)
- Цепочка: ABL артикул → `abl_products` → `product_catalog` → GUID → IIKO

1С и другие поставщики используют другой формат Excel и другие артикулы.

## Ключевой факт из IIKO API
`POST /resto/api/documents/import/incomingInvoice` принимает **два варианта** идентификации товара:
- `<product>GUID</product>` — текущий ABL-подход
- `<productArticle>АРТ-001</productArticle>` — артикул из IIKO (приоритет у GUID)

В таблице `product_catalog` уже есть поле `product_article` (= `Product.Num` в OLAP).
Если артикулы в накладной от 1С совпадают с IIKO артикулами → маппинг не нужен.

## Что нужно реализовать

### 1. Новый парсер `parse_generic_invoice()`
Для "свободного" Excel (один лист без HEADER/DETAILS).
1С обычно экспортирует с колонками:
- Артикул / Код / Номенклатура
- Наименование
- Ед.изм.
- Количество
- Цена (без НДС)
- Сумма (без НДС)
- НДС %
- Сумма НДС
- Итого с НДС

Парсер должен искать колонки по нескольким вариантам названий (нечёткий поиск).

### 2. Изменить `post-to-iiko`
Добавить логику: если нет `product_iiko_id` (GUID), использовать `productArticle`:
```python
if prod and prod.product_iiko_id:
    xml_lines.append(f"<product>{prod.product_iiko_id}</product>")
elif item.iiko_article:
    xml_lines.append(f"<productArticle>{item.iiko_article}</productArticle>")
else:
    skipped.append(item.name)
    continue
```

### 3. Добавить выбор формата при загрузке
- `format=abl` → текущий парсер
- `format=generic` → новый парсер (1С и другие)

### 4. InvoiceItem — добавить поле `iiko_article`
Хранить артикул из файла напрямую, без обязательного маппинга через `abl_products`.

## Перед реализацией нужно
- Пример Excel-файла от 1С (хотя бы скриншот шапки)
- Убедиться, что артикулы в 1С совпадают с артикулами в IIKO

## Файлы для изменения
- `backend/app/services/invoice_parser.py` — добавить `parse_generic_invoice()`
- `backend/app/api/invoices.py` — поддержка `format`, использование `productArticle`
- `backend/app/models/catalog.py` — поле `iiko_article` в `InvoiceItem`
- `backend/alembic/versions/` — миграция для нового поля
- `frontend/src/pages/InvoicesPage.tsx` — выбор формата в форме загрузки
