"""
OCR накладных через Claude Sonnet Vision API.
Принимает байты фото (JPEG/PNG/WebP) или PDF, возвращает структурированный dict.
"""
import io
import os
import base64
import json
import logging
import re
from datetime import date

logger = logging.getLogger(__name__)

def _build_system_prompt() -> str:
    current_year = date.today().year
    return f"""Ты эксперт по распознаванию казахстанских накладных на отпуск запасов на сторону.

СТРОГИЕ ПРАВИЛА:
1. Извлекай данные ТОЛЬКО из того что видишь. Если поле не читается — ставь null.
2. НИКОГДА не выдумывай данные, цифры, коды товаров.
3. Числа: десятичный разделитель — ТОЧКА (770.00, не 770,00).
4. Даты: строго формат YYYY-MM-DD. ТЕКУЩИЙ ГОД = {current_year}. Если год на документе выглядит как опечатка (например {current_year + 2} вместо {current_year}), исправь его на {current_year} и укажи в warnings.
5. Коды товаров (например УТ-00001716): копируй СИМВОЛ В СИМВОЛ.
6. Возвращай ТОЛЬКО валидный JSON — без markdown-обёрток, без текста вне JSON."""

_USER_PROMPT = """Распознай эту накладную. Верни строго JSON по схеме ниже (null если поле не видно):

{
  "document": {
    "number": "УТ-4301",
    "date": "2026-04-21"
  },
  "supplier": {
    "name": "Baker Foods ТОО",
    "bin_iin": "200640031528"
  },
  "recipient": {
    "name": "ИП CO ARENA PARK",
    "organization_note": "original coffee Байтурсынова 67 кухня"
  },
  "items": [
    {
      "line_number": 1,
      "supplier_code": "УТ-00001716",
      "name": "Маслины чёрные без косточки 280 гр/12 ж/б",
      "unit": "шт",
      "quantity": 5.0,
      "price_per_unit": 770.00,
      "total_with_vat": 3850.00,
      "vat_amount": 531.03
    }
  ],
  "totals": {
    "total_quantity": 16,
    "total_sum_with_vat": 61740.00,
    "total_vat": 8515.87
  },
  "confidence_score": 0.95,
  "warnings": []
}"""


def _fix_orientation(image_bytes: bytes) -> bytes:
    """Применяет EXIF-ориентацию к фото — исправляет повёрнутые снимки с телефона."""
    try:
        from PIL import Image, ExifTags
        img = Image.open(io.BytesIO(image_bytes))
        exif = img._getexif()
        if exif:
            orient_tag = next((k for k, v in ExifTags.TAGS.items() if v == "Orientation"), None)
            if orient_tag:
                orientation = exif.get(orient_tag)
                rotations = {3: 180, 6: 270, 8: 90}
                if orientation in rotations:
                    img = img.rotate(rotations[orientation], expand=True)
                    out = io.BytesIO()
                    img.save(out, format="JPEG", quality=92)
                    return out.getvalue()
    except Exception:
        pass
    return image_bytes


def parse_invoice_ocr(files: list[tuple[bytes, str]]) -> dict:
    """
    Отправляет одно или несколько изображений/PDF в Claude Sonnet 4.6.
    files: список (bytes, media_type) — поддерживаются JPEG/PNG/WebP/PDF.
    Все страницы передаются в один запрос, позиции объединяются.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан в переменных окружения")

    client = anthropic.Anthropic(api_key=api_key)

    has_pdf = any(mt == "application/pdf" for _, mt in files)
    extra_headers = {"anthropic-beta": "pdfs-2024-09-25"} if has_pdf else {}

    content: list[dict] = []
    for idx, (file_bytes, media_type) in enumerate(files, start=1):
        if media_type != "application/pdf":
            file_bytes = _fix_orientation(file_bytes)
        b64 = base64.standard_b64encode(file_bytes).decode("utf-8")
        logger.info("OCR file %d/%d: media_type=%s size=%d bytes", idx, len(files), media_type, len(file_bytes))
        if media_type == "application/pdf":
            content.append({
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
            })
        else:
            content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            })

    n = len(files)
    page_hint = (
        f"Тебе передано {n} страниц накладной. Распознай ВСЕ позиции со ВСЕХ страниц "
        "и объедини их в один список items. Шапку документа (номер, дата, поставщик) "
        "возьми с первой страницы.\n\n"
        if n > 1 else ""
    )
    content.append({"type": "text", "text": page_hint + _USER_PROMPT})

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        temperature=0,
        system=_build_system_prompt(),
        extra_headers=extra_headers,
        messages=[{"role": "user", "content": content}],
    )

    text = response.content[0].text.strip()
    logger.info("OCR raw response (first 300 chars): %s", text[:300])

    # Убираем markdown-обёртку если модель всё же добавила её
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("OCR JSON parse error: %s\nFull text: %s", e, text[:1000])
        raise ValueError(f"Модель вернула не-JSON ответ: {text[:200]}")

    # Валидация года даты документа
    items = data.get("items") or []
    totals = data.get("totals") or {}
    warnings = data.get("warnings") or []

    current_year = date.today().year
    doc_date_str = (data.get("document") or {}).get("date")
    if doc_date_str:
        try:
            doc_year = int(doc_date_str[:4])
            if doc_year > current_year + 1 or doc_year < current_year - 2:
                corrected = f"{current_year}{doc_date_str[4:]}"
                warnings.append(
                    f"Год в дате документа ({doc_date_str}) выглядит как опечатка — исправлен на {corrected}"
                )
                data["document"]["date"] = corrected
        except (ValueError, TypeError):
            pass

    calc_total = sum(i.get("total_with_vat") or 0 for i in items)
    doc_total = totals.get("total_sum_with_vat") or 0
    if doc_total and abs(calc_total - doc_total) > max(1.0, doc_total * 0.01):
        warnings.append(
            f"Расхождение итогов: сумма строк {calc_total:.2f} ≠ итого {doc_total:.2f}"
        )

    for item in items:
        qty = item.get("quantity") or 0
        price = item.get("price_per_unit") or 0
        total = item.get("total_with_vat") or 0
        if qty and price and total:
            expected = round(qty * price, 2)
            if abs(expected - total) > max(1.0, total * 0.01):
                warnings.append(
                    f"Строка {item.get('line_number', '?')}: "
                    f"{qty} × {price} = {expected}, но указано {total}"
                )

    data["warnings"] = warnings
    logger.info("OCR success: %d items, confidence=%.2f", len(items), data.get("confidence_score", 0))
    return data
