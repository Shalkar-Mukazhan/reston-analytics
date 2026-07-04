"""iiko API helpers for Coffee Original restaurants."""
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from app.models.co_models import CoRestaurant


def _get_key(base_url: str, login: str, password: str) -> str:
    r = requests.get(
        f"{base_url}/resto/api/auth",
        params={"login": login, "pass": password},
        timeout=20,
    )
    r.raise_for_status()
    key = r.text.strip().strip('"')
    if not key or "error" in key.lower():
        raise RuntimeError(f"iiko auth error: {r.text}")
    return key


def _fix_dates(date_from: str, date_to: str) -> tuple[str, str]:
    """iiko OLAP rejects dateFrom == dateTo — ensure dateTo is at least +1 day."""
    if date_from == date_to:
        dt = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
        date_to = dt.strftime("%Y-%m-%d")
    return date_from, date_to


def fetch_olap(restaurant: CoRestaurant, preset_id: str, date_from: str, date_to: str) -> list:
    date_from, date_to = _fix_dates(date_from, date_to)
    key = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
    url = f"{restaurant.base_url}/resto/api/v2/reports/olap/byPresetId/{preset_id}"
    params = {"key": key, "dateFrom": date_from, "dateTo": date_to}
    r = requests.get(url, params=params, timeout=120)
    if r.status_code in (401, 403):
        params["key"] = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
        r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        return data.get("data", []) or data.get("items", []) or []
    return data if isinstance(data, list) else []


def fetch_incoming_invoices(
    restaurant: CoRestaurant, supplier_iiko_id: str, date_from: str, date_to: str,
) -> list[dict]:
    """Выгрузка приходных накладных поставщика напрямую из iiko (без OLAP).

    GET /resto/api/documents/export/incomingInvoice?supplierId=...
    Возвращает по каждому документу: iiko id, внутренний и внешний номер,
    дату оприходования и сумму (Σ item.sum).
    """
    key = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
    url = f"{restaurant.base_url}/resto/api/documents/export/incomingInvoice"
    params = {"key": key, "from": date_from, "to": date_to, "supplierId": supplier_iiko_id}
    r = requests.get(url, params=params, timeout=60)
    if r.status_code in (401, 403):
        params["key"] = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
        r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    result = []
    for doc in root.findall("document"):
        items = doc.findall("items/item")
        total = sum(float(i.findtext("sum") or 0) for i in items)
        date_raw = doc.findtext("incomingDate") or ""
        result.append({
            "iiko_id": doc.findtext("id"),
            "document_number": doc.findtext("documentNumber"),
            "incoming_document_number": doc.findtext("incomingDocumentNumber"),
            "date": date_raw[:10] or None,
            "total": round(total, 2),
            "status": doc.findtext("status"),
        })
    return result


def post_writeoff(restaurant: CoRestaurant, payload: dict) -> dict:
    key = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
    url = f"{restaurant.base_url}/resto/api/v2/documents/writeoff"
    r = requests.post(url, params={"key": key}, json=payload, timeout=180)
    if r.status_code in (401, 403):
        key = _get_key(restaurant.base_url, restaurant.iiko_login, restaurant.iiko_password_hash)
        r = requests.post(url, params={"key": key}, json=payload, timeout=180)
    if not r.ok:
        raise RuntimeError(f"{r.status_code} {r.reason}: {r.text[:500]}")
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}
