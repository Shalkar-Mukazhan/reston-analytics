"""
Celery задачи для синхронизации чек-листов с Google Sheets.

Заменяет GitHub Actions (iiko_sync.py) — всё работает на нашем сервере.

Расписание (Asia/Almaty UTC+5):
  - Каждый час:  sync_checklist_hourly  — факт из IIKO → Google Sheets
  - В 07:00:     checklist_morning_reset — очистка + план → Google Sheets

Логика плана:
  1. Сначала проверяем нашу БД (sales_daily_plans) — там могут быть
     корректировки директора
  2. Если нет — считаем взвешенное среднее из IIKO истории (как iiko_sync.py)
"""
import json
import logging
import os
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

log = logging.getLogger(__name__)

ALMATY_TZ = timezone(timedelta(hours=5))

# Казахстанские праздники (месяц, день) — из iiko_sync.py
KZ_HOLIDAYS: set = {
    (1,  1), (1,  2), (1,  7),
    (3,  8), (3, 21), (3, 22), (3, 23),
    (5,  1), (5,  7), (5,  9),
    (7,  6), (8, 30), (10, 25),
    (12,  1), (12, 16), (12, 17),
}

# Настройки листов (имена и часы — как в iiko_sync.py)
SHIFT_SHEETS = {
    "Утро":  list(range(7, 16)),
    "Вечер": list(range(16, 24)),
    "Ночь":  list(range(0, 7)),
}

# Колонки в почасовых листах (1-based, как в iiko_sync.py)
COL_GC_TOTAL   = 3   # C
COL_GC_COUNTER = 5   # E
COL_GC_DRIVE   = 7   # G
COL_GC_KIOSK   = 9   # I
COL_GC_DLV     = 13  # M
COL_GC_CAFE    = 15  # O
COL_SALES      = 17  # Q
COL_AVGCHECK   = 18  # R

COL_PLAN_GC_TOTAL   = 2
COL_PLAN_GC_COUNTER = 4
COL_PLAN_GC_DRIVE   = 6
COL_PLAN_GC_KIOSK   = 8
COL_PLAN_GC_DLV     = 12
COL_PLAN_GC_CAFE    = 14
COL_PLAN_SALES      = 16

DAILY_SHEET    = "Цели на День"
DAILY_COL_TODAY = 4   # D
DAILY_COL_PREV  = 2   # B
DAILY_COL_PLAN  = 3   # C

DAILY_ROW = {
    "sales": 5, "gc": 6, "avg_check": 7,
    "pct_dt": 10, "pct_kiosk": 11, "pct_cafe": 12,
    "pct_dlv": 13, "pct_mobile": 14,
}

DAILY_COL_DONE = 5   # E — "Выполнено на X%"

CLEAR_RANGES = {
    "Утро":  ["C4:C13","E4:E13","G4:G13","I4:I13","M4:M13","O4:O13","Q4:Q13","R4:R13"],
    "Вечер": ["C4:C12","E4:E12","G4:G12","I4:I12","M4:M12","O4:O12","Q4:Q12","R4:R12"],
    "Ночь":  ["C4:C11","E4:E11","G4:G11","I4:I11","M4:M11","O4:O11","Q4:Q11","R4:R11"],
}


# ── Google Sheets клиент ──────────────────────────────────────────────────────

def _sheets_client():
    """Возвращает авторизованный gspread клиент."""
    import gspread
    from google.oauth2.service_account import Credentials

    # Сначала пробуем файл (надёжнее env_file для JSON с спецсимволами)
    cred_file = os.path.join(os.path.dirname(__file__), "..", "..", "google_credentials.json")
    cred_file = os.path.normpath(cred_file)

    if os.path.isfile(cred_file):
        try:
            creds = Credentials.from_service_account_file(
                cred_file,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            log.info("Google Sheets: авторизация через файл %s", cred_file)
            return gspread.authorize(creds)
        except Exception as e:
            log.error("Ошибка авторизации Google Sheets (файл): %s", e)
            return None

    # Запасной вариант: переменная окружения
    sa_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not sa_json:
        log.warning("google_credentials.json не найден и GOOGLE_SERVICE_ACCOUNT_JSON не задан — Google Sheets недоступны")
        return None

    try:
        info = json.loads(sa_json)
        creds = Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        return gspread.authorize(creds)
    except Exception as e:
        log.error("Ошибка авторизации Google Sheets (env): %s", e)
        return None


def _get_spreadsheet(gc, sheet_id: str):
    """Открывает таблицу по ID."""
    try:
        return gc.open_by_key(sheet_id)
    except Exception as e:
        log.error("Не удалось открыть Google Sheet %s: %s", sheet_id, e)
        return None


def _col_letter_to_num(col: str) -> int:
    result = 0
    for ch in col.upper():
        result = result * 26 + (ord(ch) - ord('A') + 1)
    return result


def _range_false_values(range_str: str) -> list:
    """Возвращает 2D-массив False нужного размера для заданного диапазона (A1:B3 и т.п.)."""
    import re
    m = re.match(r'([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)', range_str)
    if not m:
        return [[False]]
    cols = _col_letter_to_num(m.group(3)) - _col_letter_to_num(m.group(1)) + 1
    rows = int(m.group(4)) - int(m.group(2)) + 1
    return [[False] * cols for _ in range(rows)]


# Конфигурация очистки листов
CLEAR_CONFIG = {
    "ПОДГОТОВКА К СМЕНЕ": {
        "checkboxes": ["A6:B14", "A16:B19", "A21:B26", "A28:B33", "A35:B38"],
        "clear":      ["E6:F38"],
    },
    "Цели на День": {
        "checkboxes": [],
        "clear":      ["B8:E9", "B15:E18", "A22:E22", "A24:E24", "A26:E26"],
    },
    "В ТЕЧЕНИЕ СМЕНЫ": {
        "checkboxes": ["A3:B8", "A19:B22", "A24:B26", "A28:B32", "A34:B36", "A39:A41"],
        "clear":      [],
    },
    "Утро": {
        "checkboxes": [],
        "clear":      ["A17:T17", "A19:T19", "A21:T21"],
    },
    "Вечер": {
        "checkboxes": [],
        "clear":      ["A16:T16", "A18:T18", "A20:T20"],
    },
    "Ночь": {
        "checkboxes": ["A14:B19"],
        "clear":      [],
    },
    "ПОСЛЕ СМЕНЫ/ИТОГИ": {
        "checkboxes": [],
        "clear":      ["A3:I8", "A10:I16", "A18:I26"],
    },
    "ФОТО": {
        "checkboxes": [],
        "clear":      ["A1:I26"],
    },
}


def _delete_floating_images(spreadsheet, sheet_names: list) -> int:
    """Удаляет все плавающие изображения с указанных листов через Sheets API v4."""
    import requests as http_req
    from google.auth.transport.requests import Request

    try:
        creds = spreadsheet.client.auth
        if not creds.valid:
            creds.refresh(Request())
        token = creds.token
    except Exception as e:
        log.warning("Не удалось получить токен для удаления фото: %s", e)
        return 0

    sid = spreadsheet.id
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # Получаем все листы без фильтрации полей — чтобы видеть полную структуру
    try:
        resp = http_req.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sid}",
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning("Ошибка получения данных таблицы: %s", e)
        return 0

    # Логируем все листы — чтобы видеть точные названия
    all_titles = [s.get("properties", {}).get("title", "") for s in data.get("sheets", [])]
    log.info("Все листы в таблице: %s", all_titles)

    delete_requests = []
    for sheet in data.get("sheets", []):
        title = sheet.get("properties", {}).get("title", "")
        if title not in sheet_names:
            continue
        sheet_id = sheet.get("properties", {}).get("sheetId")
        log.info("  Ищем изображения на листе '%s' (id=%s), ключи: %s",
                 title, sheet_id, list(sheet.keys()))

        # Floating images могут быть в разных полях в зависимости от версии API
        for img in sheet.get("images", []):
            img_id = img.get("imageId") or img.get("objectId")
            if img_id is not None:
                delete_requests.append({"deleteEmbeddedObject": {"objectId": img_id}})
                log.info("    + image id=%s", img_id)

        for chart in sheet.get("charts", []):
            chart_id = chart.get("chartId")
            if chart_id is not None:
                delete_requests.append({"deleteEmbeddedObject": {"objectId": chart_id}})
                log.info("    + chart id=%s", chart_id)

    if not delete_requests:
        log.info("Плавающих объектов не найдено на листах: %s", sheet_names)
        return 0

    try:
        resp2 = http_req.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate",
            headers=headers,
            json={"requests": delete_requests},
            timeout=15,
        )
        resp2.raise_for_status()
        log.info("Удалено объектов: %d", len(delete_requests))
        return len(delete_requests)
    except Exception as e:
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass
        log.warning("Ошибка удаления: %s | %s", e, body)
        return 0


def _clear_spreadsheet(spreadsheet):
    """Очищает все дневные ячейки: чекбоксы → False, остальные → пусто, фото → удалено."""
    cleared = []
    for sheet_name, cfg in CLEAR_CONFIG.items():
        try:
            ws = spreadsheet.worksheet(sheet_name)
        except Exception as e:
            log.warning("Лист '%s' не найден: %s", sheet_name, e)
            continue

        if cfg["checkboxes"]:
            updates = [{"range": r, "values": _range_false_values(r)} for r in cfg["checkboxes"]]
            ws.batch_update(updates, value_input_option="RAW")

        if cfg["clear"]:
            ws.batch_clear(cfg["clear"])

        cleared.append(sheet_name)
        log.info("  Очищен лист '%s'", sheet_name)

    # Удаляем плавающие изображения только с листа "ФОТО"
    _delete_floating_images(spreadsheet, ["ФОТО"])
    return cleared


# ── IIKO helpers ─────────────────────────────────────────────────────────────

def _classify_group(name: str) -> str:
    if not name:
        return "other"
    n = name.upper()
    if "DT" in n:          return "dt"
    if "DLV" in n:         return "dlv"
    if "CAFE" in n:        return "cafe"
    if n.startswith("KZ"): return "kiosk"
    return "other"


def _parse_hourly(rows: list) -> dict:
    """Парсит почасовые строки IIKO OLAP → dict[hour → stats]."""
    data: dict = {}
    for row in rows:
        group = row.get("RestorauntGroup", "") or ""
        try:
            hour = int(row.get("HourClose", ""))
        except (ValueError, TypeError):
            continue
        gc    = int(float(row.get("UniqOrderId",       0) or 0))
        sales = float(row.get("DishDiscountSumInt", 0) or 0)

        if hour not in data:
            data[hour] = {"total_gc": 0, "total_sales": 0.0,
                          "dt_gc": 0, "dlv_gc": 0, "cafe_gc": 0, "kiosk_gc": 0}
        data[hour]["total_gc"]    += gc
        data[hour]["total_sales"] += sales

        cat = _classify_group(group)
        if   cat == "dt":    data[hour]["dt_gc"]    += gc
        elif cat == "dlv":   data[hour]["dlv_gc"]   += gc
        elif cat == "cafe":  data[hour]["cafe_gc"]  += gc
        elif cat == "kiosk": data[hour]["kiosk_gc"] += gc

    for d in data.values():
        tgc = d["total_gc"]
        d["counter_gc"] = tgc - d["dt_gc"] - d["dlv_gc"] - d["cafe_gc"] - d["kiosk_gc"]
        d["avg_check"]  = round(d["total_sales"] / tgc, 2) if tgc else 0
    return data


def _parse_daily(rows: list) -> dict:
    """Парсит дневные строки IIKO OLAP → итоги за день."""
    totals: dict = {"total_gc": 0, "total_sales": 0.0,
                    "dt_gc": 0, "dlv_gc": 0, "cafe_gc": 0, "kiosk_gc": 0, "mobile_gc": 0}
    for row in rows:
        group = row.get("RestorauntGroup", "") or ""
        gc    = int(float(row.get("UniqOrderId",       0) or 0))
        sales = float(row.get("DishDiscountSumInt", 0) or 0)
        totals["total_gc"]    += gc
        totals["total_sales"] += sales
        cat = _classify_group(group)
        if   cat == "dt":    totals["dt_gc"]    += gc
        elif cat == "dlv":   totals["dlv_gc"]   += gc
        elif cat == "cafe":  totals["cafe_gc"]  += gc
        elif cat == "kiosk": totals["kiosk_gc"] += gc

    tgc = totals["total_gc"]
    totals["avg_check"] = round(totals["total_sales"] / tgc, 2) if tgc else 0
    return totals


def _daily_from_hourly(hourly_data: dict) -> dict:
    """Суммирует почасовые данные в дневной итог (с разбивкой по каналам)."""
    totals = {"total_gc": 0, "total_sales": 0.0,
              "dt_gc": 0, "dlv_gc": 0, "cafe_gc": 0, "kiosk_gc": 0, "mobile_gc": 0}
    for h in hourly_data.values():
        totals["total_gc"]    += h.get("total_gc", 0)
        totals["total_sales"] += h.get("total_sales", 0.0)
        totals["dt_gc"]       += h.get("dt_gc", 0)
        totals["dlv_gc"]      += h.get("dlv_gc", 0)
        totals["cafe_gc"]     += h.get("cafe_gc", 0)
        totals["kiosk_gc"]    += h.get("kiosk_gc", 0)
    tgc = totals["total_gc"]
    totals["avg_check"] = round(totals["total_sales"] / tgc, 2) if tgc else 0
    return totals


def _weighted_average_hourly(datasets: list) -> dict:
    if not datasets:
        return {}
    n = len(datasets)
    weights = list(range(n, 0, -1))
    total_w = sum(weights)
    all_hours: set = set()
    for ds in datasets:
        all_hours.update(ds.keys())

    result = {}
    fields = ["total_gc", "total_sales", "counter_gc", "dt_gc", "dlv_gc", "cafe_gc", "kiosk_gc"]
    for hour in all_hours:
        r = {}
        for f in fields:
            r[f] = round(sum(weights[i] * datasets[i].get(hour, {}).get(f, 0)
                             for i in range(n)) / total_w)
        r["avg_check"] = round(r["total_sales"] / r["total_gc"], 2) if r["total_gc"] else 0
        result[hour] = r
    return result


def _weighted_average_daily(datasets: list) -> dict:
    if not datasets:
        return {}
    n = len(datasets)
    weights = list(range(n, 0, -1))
    total_w = sum(weights)
    fields = ["total_gc", "total_sales", "dt_gc", "dlv_gc", "cafe_gc", "kiosk_gc", "mobile_gc"]
    result = {f: round(sum(weights[i] * datasets[i].get(f, 0) for i in range(n)) / total_w)
              for f in fields}
    tgc = result["total_gc"]
    result["avg_check"] = round(result["total_sales"] / tgc, 2) if tgc else 0
    return result


def _get_plan_dates(today: date, n: int = 8) -> list:
    """Последние N дат того же дня недели (не праздники)."""
    result = []
    d = today - timedelta(days=7)
    while len(result) < n:
        if d.weekday() == today.weekday() and (d.month, d.day) not in KZ_HOLIDAYS:
            result.append(d)
        d -= timedelta(days=7)
    return result


# ── Google Sheets writers ─────────────────────────────────────────────────────

def _find_row(col_a: list, label: str) -> int:
    for i, v in enumerate(col_a, start=1):
        if str(v).strip() == label:
            return i
    return -1


def _cell(row: int, col: int) -> str:
    import gspread
    return gspread.utils.rowcol_to_a1(row, col)


def _hour_label(hour: int) -> str:
    return "00-1" if hour == 0 else f"{hour}-{hour + 1}"


def _update_hourly_fact(ws, hours_data: dict, shift_hours: list):
    import gspread
    col_a = ws.col_values(1)
    updates = []
    cum = defaultdict(float)

    for hour in shift_hours:
        row = _find_row(col_a, _hour_label(hour))
        if row == -1:
            continue
        d = hours_data.get(hour, {})
        gc    = d.get("total_gc", 0)
        sales = d.get("total_sales", 0.0)
        cum["gc"]      += gc
        cum["sales"]   += sales
        cum["counter"] += d.get("counter_gc", 0)
        cum["drive"]   += d.get("dt_gc", 0)
        cum["kiosk"]   += d.get("kiosk_gc", 0)
        cum["dlv"]     += d.get("dlv_gc", 0)
        cum["cafe"]    += d.get("cafe_gc", 0)

        updates += [
            {"range": _cell(row, COL_GC_TOTAL),   "values": [[gc]]},
            {"range": _cell(row, COL_GC_COUNTER), "values": [[d.get("counter_gc", 0)]]},
            {"range": _cell(row, COL_GC_DRIVE),   "values": [[d.get("dt_gc", 0)]]},
            {"range": _cell(row, COL_GC_KIOSK),   "values": [[d.get("kiosk_gc", 0)]]},
            {"range": _cell(row, COL_GC_DLV),     "values": [[d.get("dlv_gc", 0)]]},
            {"range": _cell(row, COL_GC_CAFE),    "values": [[d.get("cafe_gc", 0)]]},
            {"range": _cell(row, COL_SALES),      "values": [[round(sales, 2)]]},
            {"range": _cell(row, COL_AVGCHECK),   "values": [[d.get("avg_check", 0)]]},
        ]

    itog_row = _find_row(col_a, "ИТОГ")
    if itog_row != -1 and cum["gc"] > 0:
        updates += [
            {"range": _cell(itog_row, COL_GC_TOTAL),   "values": [[int(cum["gc"])]]},
            {"range": _cell(itog_row, COL_GC_COUNTER), "values": [[int(cum["counter"])]]},
            {"range": _cell(itog_row, COL_GC_DRIVE),   "values": [[int(cum["drive"])]]},
            {"range": _cell(itog_row, COL_GC_KIOSK),   "values": [[int(cum["kiosk"])]]},
            {"range": _cell(itog_row, COL_GC_DLV),     "values": [[int(cum["dlv"])]]},
            {"range": _cell(itog_row, COL_GC_CAFE),    "values": [[int(cum["cafe"])]]},
            {"range": _cell(itog_row, COL_SALES),      "values": [[round(cum["sales"], 2)]]},
            {"range": _cell(itog_row, COL_AVGCHECK),
             "values": [[round(cum["sales"] / cum["gc"], 2)]]},
        ]

    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    log.info("  [%s] факт: %d ячеек", ws.title, len(updates))


def _update_hourly_plan(ws, plan_data: dict, shift_hours: list):
    col_a = ws.col_values(1)
    updates = []
    cum = defaultdict(int)

    for hour in shift_hours:
        row = _find_row(col_a, _hour_label(hour))
        if row == -1 or hour not in plan_data:
            continue
        d = plan_data[hour]
        for f in ["total_gc", "total_sales", "counter_gc", "dt_gc", "kiosk_gc", "dlv_gc", "cafe_gc"]:
            cum[f] += d.get(f, 0)

        updates += [
            {"range": _cell(row, COL_PLAN_GC_TOTAL),   "values": [[d.get("total_gc",   0)]]},
            {"range": _cell(row, COL_PLAN_GC_COUNTER), "values": [[d.get("counter_gc", 0)]]},
            {"range": _cell(row, COL_PLAN_GC_DRIVE),   "values": [[d.get("dt_gc",      0)]]},
            {"range": _cell(row, COL_PLAN_GC_KIOSK),   "values": [[d.get("kiosk_gc",   0)]]},
            {"range": _cell(row, COL_PLAN_GC_DLV),     "values": [[d.get("dlv_gc",     0)]]},
            {"range": _cell(row, COL_PLAN_GC_CAFE),    "values": [[d.get("cafe_gc",    0)]]},
            {"range": _cell(row, COL_PLAN_SALES),      "values": [[round(d.get("total_sales", 0), 2)]]},
        ]

    itog_row = _find_row(col_a, "ИТОГ")
    if itog_row != -1 and cum["total_gc"] > 0:
        updates += [
            {"range": _cell(itog_row, COL_PLAN_GC_TOTAL),   "values": [[cum["total_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_GC_COUNTER), "values": [[cum["counter_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_GC_DRIVE),   "values": [[cum["dt_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_GC_KIOSK),   "values": [[cum["kiosk_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_GC_DLV),     "values": [[cum["dlv_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_GC_CAFE),    "values": [[cum["cafe_gc"]]]},
            {"range": _cell(itog_row, COL_PLAN_SALES),
             "values": [[round(cum["total_sales"], 2)]]},
        ]

    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    log.info("  [%s] план: %d ячеек", ws.title, len(updates))


def _write_daily_done_formulas(ws):
    """Колонка E листа Цели на День: =IF(C{row}>0; "Выполнено "&ROUND(D{row}/C{row}*100;1)&"%"; "-")"""
    updates = []
    for row in DAILY_ROW.values():
        # Русскоязычная Google Sheets использует точку с запятой (;) вместо запятой
        # Добавляем "Выполнено " перед процентом
        formula = f'=IF(C{row}>0;"Выполнено "&ROUND(D{row}/C{row}*100;1)&"%";"-")'
        updates.append({"range": _cell(row, DAILY_COL_DONE), "values": [[formula]]})
    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    log.info("  [%s] формулы %% выполнения: %d ячеек", ws.title, len(updates))


def _update_daily(ws, data: dict, col: int):
    tgc = data["total_gc"]
    def pct(v): return round(v / tgc * 100, 1) if tgc else 0
    updates = [
        {"range": _cell(DAILY_ROW["sales"],     col), "values": [[round(data["total_sales"], 2)]]},
        {"range": _cell(DAILY_ROW["gc"],        col), "values": [[tgc]]},
        {"range": _cell(DAILY_ROW["avg_check"], col), "values": [[data["avg_check"]]]},
        {"range": _cell(DAILY_ROW["pct_dt"],    col), "values": [[pct(data["dt_gc"])]]},
        {"range": _cell(DAILY_ROW["pct_kiosk"], col), "values": [[pct(data["kiosk_gc"])]]},
        {"range": _cell(DAILY_ROW["pct_cafe"],  col), "values": [[pct(data["cafe_gc"])]]},
        {"range": _cell(DAILY_ROW["pct_dlv"],   col), "values": [[pct(data["dlv_gc"])]]},
        {"range": _cell(DAILY_ROW["pct_mobile"],col), "values": [[pct(data.get("mobile_gc", 0))]]},
    ]
    ws.batch_update(updates, value_input_option="USER_ENTERED")
    log.info("  [%s] col %d: %d ячеек", ws.title, col, len(updates))


# ── Основная логика синхронизации одного ресторана ───────────────────────────

def _sync_restaurant(db, restaurant, sheet_id: str, is_morning: bool, business_date: date):
    """
    Синхронизирует один ресторан:
    - Каждый час: факт из IIKO → Google Sheets
    - В 07:00: очистка + план из нашей БД или IIKO истории → Google Sheets
    """
    from app.services.iiko import fetch_olap, get_session_key
    from app.models.restaurant import PresetDefinition
    from app.models.planning import SalesDailyPlan, SalesDailyFact
    import requests as req

    log.info("Sync %s (sheet=%s, morning=%s, date=%s)",
             restaurant.name, sheet_id, is_morning, business_date)

    # Получаем пресеты
    hourly_preset = restaurant.get_preset("Aim with hour")

    if not hourly_preset:
        p = db.query(PresetDefinition).filter(
            PresetDefinition.preset_type == "Aim with hour"
        ).first()
        if p:
            hourly_preset = p.preset_uuid

    if not hourly_preset:
        log.warning("%s: нет пресета 'Aim with hour', пропускаем", restaurant.name)
        return

    # Google Sheets клиент
    gc_client = _sheets_client()
    if not gc_client:
        return
    spreadsheet = _get_spreadsheet(gc_client, sheet_id)
    if not spreadsheet:
        return

    # ── ФАКТ: почасовые данные текущего дня ──
    date_from = business_date.strftime("%Y-%m-%dT00:00:00")
    date_to   = (business_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

    try:
        hourly_rows = fetch_olap(db, restaurant, hourly_preset, date_from, date_to)
    except Exception as e:
        log.error("%s: ошибка IIKO hourly: %s", restaurant.name, e)
        hourly_rows = []

    # Фильтр по department
    dept = restaurant.department_name or restaurant.name
    hourly_rows = [r for r in hourly_rows if r.get("Department") == dept]
    hours_data = _parse_hourly(hourly_rows)
    log.info("%s: факт — %d часов с данными", restaurant.name, len(hours_data))

    # ── Сохраняем дневной факт в sales_daily_facts (планирование) ──
    # Данные уже есть в памяти — ноль новых запросов к IIKO
    if hours_data:
        day_totals = _daily_from_hourly(hours_data)
        if day_totals["total_gc"] > 0:
            from datetime import timezone as _tz
            gc    = day_totals["total_gc"]
            sales = round(day_totals["total_sales"], 2)
            av    = round(sales / gc, 2) if gc > 0 else 0
            existing_fact = db.query(SalesDailyFact).filter(
                SalesDailyFact.restaurant_id == restaurant.id,
                SalesDailyFact.date == business_date,
            ).first()
            if existing_fact:
                existing_fact.gc_fact    = gc
                existing_fact.sales_fact = sales
                existing_fact.av_check_fact = av
                existing_fact.synced_at  = datetime.now(_tz.utc)
            else:
                db.add(SalesDailyFact(
                    restaurant_id=restaurant.id,
                    date=business_date,
                    gc_fact=gc,
                    sales_fact=sales,
                    av_check_fact=av,
                ))
            try:
                db.commit()
                log.info("%s: sales_daily_facts обновлён — GC=%d Sales=%s",
                         restaurant.name, gc, sales)
            except Exception as e:
                db.rollback()
                log.error("%s: ошибка сохранения sales_daily_facts: %s", restaurant.name, e)

    # ── УТРЕННИЙ СБРОС (07:00) ──
    if is_morning:
        # Очистка
        for sheet_name, ranges in CLEAR_RANGES.items():
            try:
                spreadsheet.worksheet(sheet_name).batch_clear(ranges)
            except Exception:
                pass
        try:
            ws_daily_clr = spreadsheet.worksheet(DAILY_SHEET)
            ws_daily_clr.batch_clear(["B5:B14", "D5:D14", "E5:E14"])
            _write_daily_done_formulas(ws_daily_clr)
        except Exception as e:
            log.error("%s: ошибка очистки/формул Цели на День: %s", restaurant.name, e)
        log.info("%s: листы очищены", restaurant.name)

        # Записываем текущую бизнес-дату в D1:E1 листа ПОДГОТОВКА К СМЕНЕ
        try:
            ws_prep = spreadsheet.worksheet("ПОДГОТОВКА К СМЕНЕ")
            date_str = business_date.strftime("%d.%m.%Y")
            ws_prep.update("D1:E1", [[f"Дата: {date_str}"]], value_input_option="USER_ENTERED")
            log.info("%s: дата '%s' записана в ПОДГОТОВКА К СМЕНЕ D1", restaurant.name, date_str)
        except Exception as e:
            log.error("%s: ошибка записи даты в ПОДГОТОВКА К СМЕНЕ: %s", restaurant.name, e)

        # ── ПРЕДЫДУЩИЙ ДЕНЬ: загружаем из IIKO с разбивкой по каналам ──
        prev_date = business_date - timedelta(days=1)
        prev_from = prev_date.strftime("%Y-%m-%dT00:00:00")
        prev_to = business_date.strftime("%Y-%m-%dT00:00:00")

        log.info("%s: загружаем предыдущий день %s из IIKO", restaurant.name, prev_date)
        try:
            prev_rows = fetch_olap(db, restaurant, hourly_preset, prev_from, prev_to)
            prev_rows = [r for r in prev_rows if r.get("Department") == dept]
            prev_hours = _parse_hourly(prev_rows)
            if prev_hours:
                prev_data = _daily_from_hourly(prev_hours)
                if prev_data["total_gc"] > 0:
                    ws_daily_prev = spreadsheet.worksheet(DAILY_SHEET)
                    _update_daily(ws_daily_prev, prev_data, DAILY_COL_PREV)
                    log.info("%s: предыдущий день записан — GC=%d Sales=%s DT=%d%% Kiosk=%d%% Cafe=%d%% DLV=%d%%",
                             restaurant.name, prev_data["total_gc"], prev_data["total_sales"],
                             round(prev_data["dt_gc"]/prev_data["total_gc"]*100) if prev_data["total_gc"] else 0,
                             round(prev_data["kiosk_gc"]/prev_data["total_gc"]*100) if prev_data["total_gc"] else 0,
                             round(prev_data["cafe_gc"]/prev_data["total_gc"]*100) if prev_data["total_gc"] else 0,
                             round(prev_data["dlv_gc"]/prev_data["total_gc"]*100) if prev_data["total_gc"] else 0)
                else:
                    log.warning("%s: предыдущий день — нет данных (GC=0)", restaurant.name)
            else:
                log.warning("%s: предыдущий день — нет почасовых данных", restaurant.name)
        except Exception as e:
            log.error("%s: ошибка загрузки предыдущего дня из IIKO: %s", restaurant.name, e)

        # ── ПЛАН: сначала смотрим в нашу БД ──
        db_plan = db.query(SalesDailyPlan).filter(
            SalesDailyPlan.restaurant_id == restaurant.id,
            SalesDailyPlan.date == business_date,
        ).first()

        if db_plan and db_plan.gc_plan and db_plan.sales_plan:
            log.info("%s: план из БД — GC=%s Sales=%s%s",
                     restaurant.name, db_plan.gc_plan, db_plan.sales_plan,
                     " [manual]" if db_plan.is_manual else "")
            daily_plan_data = {
                "total_gc":    db_plan.gc_plan,
                "total_sales": float(db_plan.sales_plan),
                "avg_check":   float(db_plan.av_check_plan) if db_plan.av_check_plan else
                               round(float(db_plan.sales_plan) / db_plan.gc_plan, 2),
                "dt_gc": 0, "dlv_gc": 0, "cafe_gc": 0, "kiosk_gc": 0, "mobile_gc": 0,
            }
            use_db_plan = True
        else:
            log.info("%s: плана в БД нет, считаем из IIKO истории", restaurant.name)
            use_db_plan = False
            daily_plan_data = None
        # Почасовой план из IIKO истории (нужен для листов Утро/Вечер/Ночь)
        # + дневные датасеты нужны всегда: для разбивки по каналам (даже при DB плане)
        plan_dates = _get_plan_dates(business_date, n=8)
        hourly_datasets = []
        daily_datasets  = []

        for hist_date in plan_dates:
            hf = hist_date.strftime("%Y-%m-%dT00:00:00")
            ht = (hist_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
            try:
                rows = fetch_olap(db, restaurant, hourly_preset, hf, ht)
                rows = [r for r in rows if r.get("Department") == dept]
                ds = _parse_hourly(rows)
                if ds:
                    hourly_datasets.append(ds)
                    # Суммируем почасовые в дневной — так получаем разбивку по каналам
                    dd = _daily_from_hourly(ds)
                    if dd["total_gc"] > 0:
                        daily_datasets.append(dd)
            except Exception as e:
                log.warning("%s: ошибка истории %s: %s", restaurant.name, hist_date, e)

        log.info("%s: план история — %d почасовых, %d дневных датасетов",
                 restaurant.name, len(hourly_datasets), len(daily_datasets))

        # Почасовой план → листы Утро/Вечер/Ночь
        if hourly_datasets:
            plan_hourly = _weighted_average_hourly(hourly_datasets)
            for sheet_name, shift_hours in SHIFT_SHEETS.items():
                try:
                    ws = spreadsheet.worksheet(sheet_name)
                    _update_hourly_plan(ws, plan_hourly, shift_hours)
                except Exception as e:
                    log.error("  [%s] план ошибка: %s", sheet_name, e)

        # Дневной план → лист Цели на День
        if use_db_plan and daily_datasets and daily_plan_data:
            # Есть план из БД — берём разбивку по каналам из истории IIKO
            # и применяем пропорционально к нашему плановому GC
            hist_avg = _weighted_average_daily(daily_datasets)
            hist_gc = hist_avg["total_gc"]
            if hist_gc > 0:
                gc = daily_plan_data["total_gc"]
                daily_plan_data["dt_gc"]    = round(hist_avg["dt_gc"]    / hist_gc * gc)
                daily_plan_data["kiosk_gc"] = round(hist_avg["kiosk_gc"] / hist_gc * gc)
                daily_plan_data["cafe_gc"]  = round(hist_avg["cafe_gc"]  / hist_gc * gc)
                daily_plan_data["dlv_gc"]   = round(hist_avg["dlv_gc"]   / hist_gc * gc)
                daily_plan_data["mobile_gc"]= round(hist_avg.get("mobile_gc", 0) / hist_gc * gc)
            log.info("%s: каналы из истории → DT=%s Kiosk=%s Cafe=%s DLV=%s",
                     restaurant.name, daily_plan_data["dt_gc"], daily_plan_data["kiosk_gc"],
                     daily_plan_data["cafe_gc"], daily_plan_data["dlv_gc"])
        elif not use_db_plan and daily_datasets:
            daily_plan_data = _weighted_average_daily(daily_datasets)

        if daily_plan_data and daily_plan_data["total_gc"] > 0:
            try:
                ws_daily = spreadsheet.worksheet(DAILY_SHEET)
                _update_daily(ws_daily, daily_plan_data, DAILY_COL_PLAN)
            except Exception as e:
                log.error("  [%s] план ошибка: %s", DAILY_SHEET, e)

    # ── ФАКТ: пишем в Google Sheets ──
    for sheet_name, shift_hours in SHIFT_SHEETS.items():
        try:
            ws = spreadsheet.worksheet(sheet_name)
            _update_hourly_fact(ws, hours_data, shift_hours)
        except Exception as e:
            log.error("  [%s] факт ошибка: %s", sheet_name, e)

    # Дневной факт → Цели на День (из уже полученных почасовых данных, без лишнего IIKO-запроса)
    if hours_data:
        daily_data = _daily_from_hourly(hours_data)
        if daily_data["total_gc"] > 0:
            try:
                ws_daily = spreadsheet.worksheet(DAILY_SHEET)
                _update_daily(ws_daily, daily_data, DAILY_COL_TODAY)
                # Обновляем формулы % выполнения каждый раз (чтобы не терялись)
                _write_daily_done_formulas(ws_daily)
            except Exception as e:
                log.error("%s: дневной факт ошибка: %s", restaurant.name, e)

    log.info("%s: синхронизация завершена", restaurant.name)


# ── Celery задачи ─────────────────────────────────────────────────────────────

from app.tasks.celery_app import celery_app
import time


@celery_app.task(name="app.tasks.checklist_tasks.sync_checklist_hourly")
def sync_checklist_hourly():
    """
    Каждый час: факт из IIKO → Google Sheets.
    Синхронизирует только рестораны где сегодня нажата кнопка 'Начать новый день'.
    Пауза 3 сек между ресторанами чтобы не перегружать IIKO.
    """
    from app.core.database import SessionLocal
    from app.models.restaurant import Restaurant

    now_almaty = datetime.now(ALMATY_TZ)
    # Бизнес дата: если до 07:00 — это ещё предыдущий день
    business_date = (now_almaty - timedelta(hours=7)).date() if now_almaty.hour < 7 \
                    else now_almaty.date()

    from app.services.telegram import alert_error
    log.info("=== checklist hourly | %s Almaty | biz_date=%s ===",
             now_almaty.strftime("%H:%M"), business_date)

    db = SessionLocal()
    try:
        restaurants = db.query(Restaurant).filter(
            Restaurant.is_active == True,
            Restaurant.google_sheet_url.isnot(None),
            Restaurant.google_sheet_url != "",
            Restaurant.last_checklist_reset_date == business_date,  # по бизнес-дате, не по календарю
        ).all()

        log.info("Активных ресторанов сегодня: %d", len(restaurants))

        for i, restaurant in enumerate(restaurants):
            if i > 0:
                time.sleep(3)   # пауза между ресторанами — не перегружаем IIKO
            sheet_id = _extract_sheet_id(restaurant.google_sheet_url)
            if not sheet_id:
                log.warning("%s: не удалось извлечь Sheet ID из %s",
                            restaurant.name, restaurant.google_sheet_url)
                continue
            try:
                _sync_restaurant(db, restaurant, sheet_id, is_morning=False,
                                 business_date=business_date)
            except Exception as e:
                log.error("Ошибка синхронизации %s: %s", restaurant.name, e)
                alert_error(f"Чек-лист: ошибка синхронизации {restaurant.name}", str(e))
    finally:
        db.close()

    log.info("=== checklist hourly done ===")


@celery_app.task(name="app.tasks.checklist_tasks.start_day_sync_task")
def start_day_sync_task(restaurant_id: int):
    """
    Запускается при нажатии кнопки 'Начать новый день'.
    Выполняет утренний сброс: очистка + план → Google Sheets.
    """
    from app.core.database import SessionLocal
    from app.models.restaurant import Restaurant

    now_almaty = datetime.now(ALMATY_TZ)
    business_date = (now_almaty - timedelta(hours=7)).date() if now_almaty.hour < 7 \
                    else now_almaty.date()

    from app.services.telegram import alert_error, alert_ok
    log.info("=== start-day sync | restaurant_id=%d | %s Almaty | biz_date=%s ===",
             restaurant_id, now_almaty.strftime("%H:%M"), business_date)

    db = SessionLocal()
    try:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not restaurant:
            log.error("Ресторан %d не найден", restaurant_id)
            return
        if not restaurant.google_sheet_url:
            log.warning("%s: google_sheet_url не задан", restaurant.name)
            return

        sheet_id = _extract_sheet_id(restaurant.google_sheet_url)
        if not sheet_id:
            log.error("%s: не удалось извлечь Sheet ID", restaurant.name)
            return

        _sync_restaurant(db, restaurant, sheet_id, is_morning=True,
                         business_date=business_date)
        alert_ok(f"Чек-лист: новый день начат — {restaurant.name}",
                 f"Дата: {business_date}, план и история загружены в Google Sheets")
    except Exception as e:
        log.error("Ошибка start-day %s: %s", restaurant_id, e)
        alert_error(f"Чек-лист: ошибка начала дня (ресторан #{restaurant_id})", str(e))
    finally:
        db.close()

    log.info("=== start-day sync done ===")


@celery_app.task(name="app.tasks.checklist_tasks.clear_sheets_task")
def clear_sheets_task(restaurant_id: int):
    """
    Очищает Google Sheets ресторана:
    - Чекбоксы → False (ПОДГОТОВКА К СМЕНЕ, В ТЕЧЕНИЕ СМЕНЫ, Ночь)
    - Обеденные и дневные ячейки → пусто
    """
    from app.core.database import SessionLocal
    from app.models.restaurant import Restaurant
    from app.services.telegram import alert_error, alert_ok

    log.info("=== clear-sheets | restaurant_id=%d ===", restaurant_id)
    db = SessionLocal()
    try:
        restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
        if not restaurant or not restaurant.google_sheet_url:
            log.error("Ресторан %d не найден или нет Google Sheet", restaurant_id)
            return

        sheet_id = _extract_sheet_id(restaurant.google_sheet_url)
        if not sheet_id:
            log.error("%s: не удалось извлечь Sheet ID", restaurant.name)
            return

        gc_client = _sheets_client()
        if not gc_client:
            return
        spreadsheet = _get_spreadsheet(gc_client, sheet_id)
        if not spreadsheet:
            return

        cleared = _clear_spreadsheet(spreadsheet)
        alert_ok(f"Чек-лист: очистка завершена — {restaurant.name}",
                 f"Очищено листов: {len(cleared)}: {', '.join(cleared)}")
        log.info("=== clear-sheets done: %s ===", ', '.join(cleared))
    except Exception as e:
        log.error("Ошибка clear-sheets %d: %s", restaurant_id, e)
        alert_error(f"Чек-лист: ошибка очистки (ресторан #{restaurant_id})", str(e))
    finally:
        db.close()


@celery_app.task(name="app.tasks.checklist_tasks.sync_planning_facts_hourly")
def sync_planning_facts_hourly():
    """
    Каждый час: обновляет sales_daily_facts для ВСЕХ активных ресторанов.
    Работает независимо от чек-листа — не требует нажатия 'Начать день'.
    Использует Redis-кеш: если ресторан уже запросился через чек-лист,
    данные берутся из кеша без повторного запроса к IIKO.
    """
    from app.core.database import SessionLocal
    from app.models.restaurant import Restaurant, PresetDefinition
    from app.models.planning import SalesDailyFact
    from app.services.iiko import fetch_olap

    now_almaty = datetime.now(ALMATY_TZ)
    business_date = (now_almaty - timedelta(hours=7)).date() if now_almaty.hour < 7 \
                    else now_almaty.date()

    log.info("=== sync_planning_facts_hourly | biz_date=%s ===", business_date)

    db = SessionLocal()
    try:
        restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()

        global_preset = db.query(PresetDefinition).filter(
            PresetDefinition.preset_type == "Aim with hour"
        ).first()

        date_from = business_date.strftime("%Y-%m-%dT00:00:00")
        date_to   = (business_date + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")

        updated = 0
        for i, restaurant in enumerate(restaurants):
            if i > 0:
                time.sleep(1)

            preset_uuid = restaurant.get_preset("Aim with hour")
            if not preset_uuid and global_preset:
                preset_uuid = global_preset.preset_uuid
            if not preset_uuid:
                continue

            try:
                rows = fetch_olap(db, restaurant, preset_uuid, date_from, date_to)
                dept = restaurant.department_name or restaurant.name
                rows = [r for r in rows if r.get("Department") == dept]
                if not rows:
                    continue

                hours_data = _parse_hourly(rows)
                if not hours_data:
                    continue

                day = _daily_from_hourly(hours_data)
                gc    = day["total_gc"]
                sales = round(day["total_sales"], 2)
                if gc <= 0:
                    continue

                av = round(sales / gc, 2)
                from datetime import timezone as _tz
                existing = db.query(SalesDailyFact).filter(
                    SalesDailyFact.restaurant_id == restaurant.id,
                    SalesDailyFact.date == business_date,
                ).first()
                if existing:
                    existing.gc_fact = gc
                    existing.sales_fact = sales
                    existing.av_check_fact = av
                    existing.synced_at = datetime.now(_tz.utc)
                else:
                    db.add(SalesDailyFact(
                        restaurant_id=restaurant.id,
                        date=business_date,
                        gc_fact=gc,
                        sales_fact=sales,
                        av_check_fact=av,
                    ))
                updated += 1
            except Exception as e:
                log.error("%s: ошибка sync_planning_facts: %s", restaurant.name, e)

        db.commit()
        log.info("=== sync_planning_facts_hourly done: %d/%d ресторанов ===",
                 updated, len(restaurants))
    except Exception as e:
        db.rollback()
        log.error("sync_planning_facts_hourly: критическая ошибка: %s", e)
    finally:
        db.close()


def _extract_sheet_id(url: str) -> str | None:
    """
    Извлекает spreadsheet ID из Google Sheets URL.
    https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit → SPREADSHEET_ID
    """
    if not url:
        return None
    # Если передан просто ID (без URL)
    if "/" not in url:
        return url.strip()
    try:
        parts = url.split("/d/")
        if len(parts) < 2:
            return None
        return parts[1].split("/")[0].strip()
    except Exception:
        return None
