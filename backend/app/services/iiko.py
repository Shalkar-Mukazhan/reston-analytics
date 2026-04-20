"""
IIKO API сервис — перенесён из app.py
Кэш сессий хранится в PostgreSQL (таблица iiko_sessions) вместо файлов на диске
OLAP результаты кэшируются в Redis на 1 час для снижения нагрузки на IIKO.
"""
import json
from datetime import datetime, timedelta, timezone
import requests
from sqlalchemy.orm import Session
from app.models.report import IikoSession


def _redis():
    """Возвращает Redis клиент. Если недоступен — возвращает None (graceful degradation)."""
    try:
        import redis as redis_lib
        from app.core.config import settings
        return redis_lib.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2)
    except Exception:
        return None


def get_session_key(db: Session, restaurant, force_refresh: bool = False) -> str:
    if not force_refresh:
        cached = (
            db.query(IikoSession)
            .filter(
                IikoSession.restaurant_id == restaurant.id,
                IikoSession.expires_at > datetime.now(timezone.utc),
            )
            .first()
        )
        if cached:
            return cached.session_key

    key = _auth_iiko(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
    _save_session(db, restaurant.id, key)
    return key


def _auth_iiko(base_url: str, login: str, password_hash: str) -> str:
    url = f"{base_url}/resto/api/auth"
    r = requests.get(
        url,
        params={"login": login, "pass": password_hash},
        timeout=30,
    )
    r.raise_for_status()
    key = r.text.strip().strip('"')
    if not key or "error" in key.lower():
        raise RuntimeError(f"IIKO AUTH вернул ошибку: {r.text}")
    return key


def _save_session(db: Session, restaurant_id: int, key: str) -> None:
    db.query(IikoSession).filter(IikoSession.restaurant_id == restaurant_id).delete()
    session = IikoSession(
        restaurant_id=restaurant_id,
        session_key=key,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(session)
    db.commit()


def _cache_ttl(date_from: str) -> int:
    """5 минут для сегодняшних данных, 1 час для прошлых дат."""
    try:
        from datetime import timezone, timedelta
        almaty = timezone(timedelta(hours=5))
        query_date = datetime.fromisoformat(date_from).date()
        today = datetime.now(almaty).date()
        return 300 if query_date >= today else 3600
    except Exception:
        return 3600


def fetch_olap(db: Session, restaurant, preset_id: str, date_from: str, date_to: str) -> list:
    cache_key = f"olap:{restaurant.id}:{preset_id}:{date_from}:{date_to}"
    rc = _redis()
    if rc:
        try:
            cached = rc.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            pass

    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/reports/olap/byPresetId/{preset_id}"
    params = {"key": key, "dateFrom": date_from, "dateTo": date_to}

    r = requests.get(url, params=params, timeout=180)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.get(url, params=params, timeout=180)

    r.raise_for_status()
    data = r.json().get("data", [])

    if rc:
        try:
            rc.setex(cache_key, _cache_ttl(date_from), json.dumps(data))
        except Exception:
            pass

    return data


def post_invoice(db: Session, restaurant, xml_body: str) -> dict:
    """POST накладной в IIKO через /resto/api/documents/import/incomingInvoice."""
    import xml.etree.ElementTree as ET

    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/documents/import/incomingInvoice"

    r = requests.post(
        url,
        params={"key": key},
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=60,
    )

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        r = requests.post(
            url,
            params={"key": key},
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            timeout=60,
        )

    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.reason}: {r.text[:400]}")

    root = ET.fromstring(r.text)
    return {
        "valid": root.findtext("valid") or "",
        "documentNumber": root.findtext("documentNumber") or "",
        "error": root.findtext("errorMessage") or "",
        "warning": root.findtext("warning") or "",
    }


def fetch_assembly_charts(db: Session, restaurant, date_from: str, date_to: str) -> list:
    """Получить все техкарты из IIKO за период. Возвращает список AssemblyChartDto."""
    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/assemblyCharts/getAll"
    params = {
        "key": key,
        "dateFrom": date_from,
        "dateTo": date_to,
        "includeDeletedProducts": "false",
        "includePreparedCharts": "false",
    }

    r = requests.get(url, params=params, timeout=180)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.get(url, params=params, timeout=180)

    r.raise_for_status()
    data = r.json()
    return data.get("assemblyCharts") or []


def fetch_products_list(db: Session, restaurant) -> list:
    """Получить список номенклатуры (блюда/заготовки) для получения имён."""
    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/entities/products/list"
    params = {"key": key, "includeDeleted": "false"}

    r = requests.get(url, params=params, timeout=60)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.get(url, params=params, timeout=60)

    if not r.ok:
        return []

    try:
        return r.json()
    except Exception:
        return []


def fetch_chart_history(db: Session, restaurant, product_uuid: str) -> list:
    """Получить все версии техкарты одного блюда (история)."""
    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/assemblyCharts/getHistory"
    params = {"key": key, "productId": product_uuid}

    r = requests.get(url, params=params, timeout=60)
    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.get(url, params=params, timeout=60)

    if not r.ok:
        return []
    try:
        return r.json() or []
    except Exception:
        return []


def save_assembly_chart(db: Session, restaurant, chart_payload: dict) -> dict:
    """Создать новую версию техкарты в IIKO (POST /assemblyCharts/save)."""
    import logging, json as _json
    log = logging.getLogger("recipes.save")

    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/assemblyCharts/save"
    params = {"key": key}

    log.warning("IIKO save payload: %s", _json.dumps(chart_payload, ensure_ascii=False)[:800])

    r = requests.post(url, params=params, json=chart_payload, timeout=60)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.post(url, params=params, json=chart_payload, timeout=60)

    log.warning("IIKO save response [%s]: %s", r.status_code, r.text[:800])

    if not r.ok:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")

    data = r.json()
    # IIKO возвращает {"result": "SUCCESS"/"ERROR", "errors": [...], "response": {...}}
    if isinstance(data, dict) and data.get("result") == "ERROR":
        errors = data.get("errors") or []
        raise RuntimeError(f"IIKO error: {errors}")

    return data


def delete_assembly_chart(db: Session, restaurant, chart_uuid: str) -> bool:
    """Удалить версию техкарты из IIKO по её UUID (POST с телом)."""
    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/assemblyCharts/delete"

    r = requests.post(url, params={"key": key}, json={"id": chart_uuid}, timeout=60)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        r = requests.post(url, params={"key": key}, json={"id": chart_uuid}, timeout=60)

    if not r.ok:
        return False
    try:
        data = r.json()
        return data.get("result") == "SUCCESS"
    except Exception:
        return r.ok


def post_writeoff(db: Session, restaurant, payload: dict) -> dict:
    key = get_session_key(db, restaurant)
    url = f"{restaurant.base_url}/resto/api/v2/documents/writeoff"
    params = {"key": key}

    r = requests.post(url, params=params, json=payload, timeout=180)

    if r.status_code in (401, 403):
        key = get_session_key(db, restaurant, force_refresh=True)
        params["key"] = key
        r = requests.post(url, params=params, json=payload, timeout=180)

    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.reason}: {r.text[:1000]}")
    try:
        return r.json()
    except Exception:
        return {"raw_response": r.text}
