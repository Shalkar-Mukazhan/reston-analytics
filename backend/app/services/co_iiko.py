"""iiko API helpers for Coffee Original restaurants."""
import time
import requests
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
