"""Telegram уведомления — алерты об ошибках."""
import logging
import os

import requests

log = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    """Отправляет сообщение в Telegram чат. Возвращает True если успешно."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        return False

    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        log.warning("Telegram отправка не удалась: %s", e)
        return False


def alert_error(title: str, details: str = "") -> None:
    """Алерт об ошибке — красный кружок + текст."""
    msg = f"🔴 <b>{title}</b>"
    if details:
        msg += f"\n<code>{details[:500]}</code>"
    send_telegram(msg)


def alert_ok(title: str, details: str = "") -> None:
    """Алерт об успехе — зелёный кружок + текст."""
    msg = f"✅ <b>{title}</b>"
    if details:
        msg += f"\n{details}"
    send_telegram(msg)
