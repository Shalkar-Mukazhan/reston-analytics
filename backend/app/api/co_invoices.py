"""
CO Накладные — OCR через Claude Vision, аналог invoices2 но для coffee_original.

POST /api/co/invoices/ocr-parse    — распознать фото/PDF (без сохранения)
POST /api/co/invoices/ocr-confirm  — сохранить после проверки
GET  /api/co/invoices/             — список
GET  /api/co/invoices/{id}/items   — позиции
POST /api/co/invoices/{id}/post-to-iiko — отправить в iiko
"""
import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenant_utils import load_restaurant
from app.api.co_auth import get_current_co_user, CoUser
from app.models.co_models import (
    CoRestaurant, CoWarehouse, CoSupplier,
    CoProduct, CoProductMapping, CoProductContainer, CoInvoice, CoInvoiceItem,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/co/invoices", tags=["co-invoices"])

_MEDIA_TYPES = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",  ".webp": "image/webp",
    ".pdf": "application/pdf",
}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _detect_media_type(filename: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    mt = _MEDIA_TYPES.get(ext)
    if not mt:
        raise HTTPException(status_code=400, detail="Поддерживаются: JPEG, PNG, WebP, PDF")
    return mt


def _check_access(user: CoUser, restaurant_id: int, db) -> None:
    load_restaurant(db, restaurant_id, user)
    if user.role == "admin":
        return
    if restaurant_id not in [r.id for r in user.restaurants]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому ресторану",
        )


# ── OCR parse ─────────────────────────────────────────────────────────────────

@router.post("/ocr-parse")
async def ocr_parse(
    restaurant_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    """Распознаёт накладную через Claude Vision. Ничего не сохраняет."""
    _check_access(user, restaurant_id, db)

    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Максимум 5 файлов")

    parsed_files: list[tuple[bytes, str]] = []
    for upload in files:
        media_type = _detect_media_type(upload.filename or "file.jpg")
        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"{upload.filename!r} слишком большой (макс. 5 МБ)")
        parsed_files.append((file_bytes, media_type))

    try:
        from app.services.ocr_service import parse_invoice_ocr
        return parse_invoice_ocr(parsed_files)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Ошибка распознавания: {e}")


# ── OCR confirm ───────────────────────────────────────────────────────────────

class OcrItemIn(BaseModel):
    line_number: int | None = None
    supplier_code: str | None = None
    name: str
    unit: str | None = None
    quantity: float
    price_per_unit: float
    total_with_vat: float
    vat_amount: float | None = None


class OcrConfirmRequest(BaseModel):
    restaurant_id: int
    warehouse_id: int
    document_number: str | None = None
    document_date: str | None = None
    supplier_name: str | None = None
    supplier_bin: str | None = None
    items: list[OcrItemIn]
    total_sum_with_vat: float | None = None


@router.post("/ocr-confirm")
def ocr_confirm(
    body: OcrConfirmRequest,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    _check_access(user, body.restaurant_id, db)
    if not db.query(CoWarehouse).filter(CoWarehouse.id == body.warehouse_id).first():
        raise HTTPException(status_code=404, detail="Склад не найден")

    # Дата
    invoice_date = None
    if body.document_date:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                invoice_date = datetime.strptime(body.document_date, fmt).date()
                break
            except ValueError:
                pass

    # Поставщик: по БИН (нормализуем — убираем пробелы из OCR) → по имени
    supplier = None
    if body.supplier_bin:
        normalized_bin = re.sub(r"\s+", "", body.supplier_bin.strip())
        supplier = db.query(CoSupplier).filter(
            CoSupplier.bin == normalized_bin,
            CoSupplier.tenant_id == user.tenant_id,
        ).first()
    if not supplier and body.supplier_name:
        supplier = db.query(CoSupplier).filter(
            CoSupplier.name.ilike(f"%{body.supplier_name[:30]}%"),
            CoSupplier.tenant_id == user.tenant_id,
        ).first()

    # Авто-маппинг по коду поставщика → iiko товар
    mapping_by_code: dict[str, int] = {}
    mapping_by_name: dict[str, int] = {}
    if supplier:
        rows = db.query(CoProductMapping).filter(CoProductMapping.supplier_id == supplier.id).all()
        for r in rows:
            if r.supplier_product_code and r.product_id:
                mapping_by_code[r.supplier_product_code.strip().lower()] = r.product_id
            if r.supplier_product_name and r.product_id:
                mapping_by_name[r.supplier_product_name.strip().lower()] = r.product_id

    invoice = CoInvoice(
        restaurant_id=body.restaurant_id,
        warehouse_id=body.warehouse_id,
        supplier_id=supplier.id if supplier else None,
        invoice_date=invoice_date or datetime.now().date(),
        document_number=body.document_number or None,
        status="draft",
        created_by=user.id,
    )

    db.add(invoice)
    db.flush()

    # Все активные товары для нечёткого поиска
    all_active = db.query(CoProduct).filter(
        CoProduct.is_active == True,
        CoProduct.tenant_id == user.tenant_id,
    ).all()

    def _fuzzy(name: str):
        words = [w for w in name.lower().split() if len(w) > 3]
        if not words:
            return None
        best, best_score = None, 0
        for p in all_active:
            score = sum(1 for w in words if w in p.name.lower())
            if score > best_score:
                best_score, best = score, p
        return best.id if best and best_score >= 1 else None

    matched = 0
    for row in body.items:
        code_key = (row.supplier_code or "").strip().lower()
        name_key = row.name.strip().lower()
        product_id = (mapping_by_code.get(code_key)
                      or mapping_by_name.get(name_key)
                      or _fuzzy(row.name))
        if product_id:
            matched += 1

        db.add(CoInvoiceItem(
            invoice_id=invoice.id,
            product_id=product_id,
            supplier_product_name=row.name,
            supplier_product_code=row.supplier_code or None,
            qty=row.quantity,
            price=row.price_per_unit,
        ))

    db.commit()
    return {
        "invoice_id": invoice.id,
        "status": invoice.status,
        "items_count": len(body.items),
        "iiko_matched": matched,
        "iiko_unmatched": len(body.items) - matched,
        "supplier_matched": supplier.name if supplier else None,
        "supplier_found": supplier is not None,
        "supplier_name_ocr": body.supplier_name or None,
    }


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/")
def list_invoices(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    accessible = [r.id for r in user.restaurants] if user.role != "admin" else None
    q = db.query(CoInvoice).join(
        CoRestaurant, CoInvoice.restaurant_id == CoRestaurant.id
    ).filter(CoRestaurant.tenant_id == user.tenant_id)
    if accessible is not None:
        q = q.filter(CoInvoice.restaurant_id.in_(accessible))
    if restaurant_id:
        q = q.filter(CoInvoice.restaurant_id == restaurant_id)

    invoices = q.order_by(CoInvoice.invoice_date.desc(), CoInvoice.id.desc()).limit(200).all()

    supplier_ids = [i.supplier_id for i in invoices if i.supplier_id]
    warehouse_ids = [i.warehouse_id for i in invoices]
    suppliers = {s.id: s for s in db.query(CoSupplier).filter(CoSupplier.id.in_(supplier_ids), CoSupplier.tenant_id == user.tenant_id).all()}
    warehouses = {w.id: w for w in db.query(CoWarehouse).filter(CoWarehouse.id.in_(warehouse_ids)).all()}

    result = []
    for inv in invoices:
        items_count = len(inv.items)
        sup = suppliers.get(inv.supplier_id)
        wh = warehouses.get(inv.warehouse_id)
        result.append({
            "id": inv.id,
            "restaurant_id": inv.restaurant_id,
            "warehouse_id": inv.warehouse_id,
            "warehouse_name": wh.name if wh else None,
            "supplier_id": inv.supplier_id,
            "supplier_name": sup.name if sup else None,
            "supplier_bin": sup.bin if sup else None,
            "invoice_date": inv.invoice_date.isoformat() if inv.invoice_date else None,
            "document_number": inv.document_number,
            "status": inv.status,
            "needs_resend": inv.needs_resend,
            "uploaded_at": inv.created_at.isoformat(),
            "items_count": items_count,
            "total_sum_vat": sum(float(i.qty) * float(i.price) for i in inv.items),
        })
    return result


# ── Items ─────────────────────────────────────────────────────────────────────

@router.get("/{inv_id}/items")
def get_items(
    inv_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    inv = db.query(CoInvoice).filter(CoInvoice.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    _check_access(user, inv.restaurant_id, db)

    product_ids = [i.product_id for i in inv.items if i.product_id]
    products = {p.id: p for p in db.query(CoProduct).filter(CoProduct.id.in_(product_ids), CoProduct.tenant_id == user.tenant_id).all()}

    # Загружаем маппинги поставщика → контейнеры
    mappings_by_name: dict[str, CoProductMapping] = {}
    mappings_by_code: dict[str, CoProductMapping] = {}
    if inv.supplier_id:
        for m in db.query(CoProductMapping).filter(CoProductMapping.supplier_id == inv.supplier_id).all():
            if m.supplier_product_name:
                mappings_by_name[m.supplier_product_name.strip().lower()] = m
            if m.supplier_product_code:
                mappings_by_code[m.supplier_product_code.strip().lower()] = m
    container_ids = {m.container_id for m in list(mappings_by_name.values()) + list(mappings_by_code.values()) if m.container_id}
    containers = {c.id: c for c in db.query(CoProductContainer).filter(CoProductContainer.id.in_(container_ids)).all()} if container_ids else {}

    result = []
    for i in inv.items:
        name_key = (i.supplier_product_name or "").strip().lower()
        code_key = (i.supplier_product_code or "").strip().lower()
        mapping = mappings_by_name.get(name_key) or mappings_by_code.get(code_key)
        container = containers.get(mapping.container_id) if mapping and mapping.container_id else None

        # Если в позиции нет product_id, но есть маппинг — берём из маппинга
        effective_product_id = i.product_id or (mapping.product_id if mapping else None)
        product = products.get(effective_product_id) if effective_product_id else None
        # Если нашли через маппинг, но не было в preloaded products — дозагружаем
        if effective_product_id and not product:
            product = db.query(CoProduct).filter(CoProduct.id == effective_product_id, CoProduct.tenant_id == user.tenant_id).first()

        qty = float(i.qty)
        iiko_qty = qty * float(container.count) if container else None

        result.append({
            "id": i.id,
            "name": i.supplier_product_name,
            "supplier_code": i.supplier_product_code or (mapping.supplier_product_code if mapping else None),
            "supplier_id": inv.supplier_id,
            "quantity": qty,
            "unit_price_vat": float(i.price),
            "total_price_vat": round(qty * float(i.price), 2),
            "iiko_product_name": product.name if product else None,
            "matched": bool(effective_product_id),
            "container_name": container.name if container else None,
            "container_count": float(container.count) if container else None,
            "iiko_qty": iiko_qty,
        })
    return result


# ── Update invoice ────────────────────────────────────────────────────────────

class UpdateInvoiceRequest(BaseModel):
    warehouse_id: int | None = None
    supplier_id: int | None = None


@router.patch("/{inv_id}")
def update_invoice(
    inv_id: int,
    body: UpdateInvoiceRequest,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    inv = db.query(CoInvoice).filter(CoInvoice.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    _check_access(user, inv.restaurant_id, db)

    result: dict = {"ok": True}

    if body.warehouse_id is not None:
        wh = db.query(CoWarehouse).filter(CoWarehouse.id == body.warehouse_id).first()
        if not wh:
            raise HTTPException(status_code=404, detail="Склад не найден")
        inv.warehouse_id = body.warehouse_id
        result["warehouse_id"] = wh.id
        result["warehouse_name"] = wh.name

    if body.supplier_id is not None:
        sup = db.query(CoSupplier).filter(
            CoSupplier.id == body.supplier_id,
            CoSupplier.tenant_id == user.tenant_id,
        ).first()
        if not sup:
            raise HTTPException(status_code=404, detail="Поставщик не найден")
        inv.supplier_id = body.supplier_id
        result["supplier_id"] = sup.id
        result["supplier_name"] = sup.name
        result["supplier_bin"] = sup.bin

    if inv.status == "sent":
        inv.needs_resend = True
    db.commit()
    return result


# ── Delete invoice ────────────────────────────────────────────────────────────

@router.delete("/{inv_id}")
def delete_invoice(
    inv_id: int,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    inv = db.query(CoInvoice).filter(CoInvoice.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    _check_access(user, inv.restaurant_id, db)
    db.delete(inv)
    db.commit()
    return {"ok": True}


# ── Post to iiko ──────────────────────────────────────────────────────────────

class PostToIikoRequest(BaseModel):
    date_incoming: str              # "dd.MM.yyyy" — дата прихода
    invoice_number: str | None = None   # Вх. номер документа
    invoice_date: str | None = None     # Дата СФ "dd.MM.yyyy"
    comment: str | None = None          # Комментарий


@router.post("/{inv_id}/post-to-iiko")
def post_to_iiko(
    inv_id: int,
    body: PostToIikoRequest,
    db: Session = Depends(get_db),
    user: CoUser = Depends(get_current_co_user),
):
    inv = db.query(CoInvoice).filter(CoInvoice.id == inv_id).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Накладная не найдена")
    _check_access(user, inv.restaurant_id, db)
    # Повторная отправка разрешена (например, после добавления маппингов для пропущенных позиций)

    restaurant = db.query(CoRestaurant).filter(CoRestaurant.id == inv.restaurant_id, CoRestaurant.tenant_id == user.tenant_id).first()
    warehouse = db.query(CoWarehouse).filter(CoWarehouse.id == inv.warehouse_id).first()
    if not warehouse or not warehouse.iiko_store_id:
        raise HTTPException(status_code=400, detail="Склад не привязан к iiko — укажите iiko_store_id в настройках склада")

    supplier = db.query(CoSupplier).filter(CoSupplier.id == inv.supplier_id, CoSupplier.tenant_id == user.tenant_id).first()
    if not supplier or not supplier.iiko_id:
        raise HTTPException(status_code=400, detail="У поставщика нет iiko UUID — выполните синхронизацию поставщиков")

    product_ids = [i.product_id for i in inv.items if i.product_id]
    products = {p.id: p for p in db.query(CoProduct).filter(CoProduct.id.in_(product_ids), CoProduct.tenant_id == user.tenant_id).all()}

    # Все продукты для нечёткого поиска по имени (фолбэк если нет маппинга)
    all_products = db.query(CoProduct).filter(
        CoProduct.is_active == True,
        CoProduct.iiko_article_id.isnot(None),
        CoProduct.tenant_id == user.tenant_id,
    ).all()

    def _fuzzy_find(name: str):
        words = [w for w in name.lower().split() if len(w) > 3]
        if not words:
            return None
        best, best_score = None, 0
        for p in all_products:
            score = sum(1 for w in words if w in p.name.lower())
            if score > best_score:
                best_score, best = score, p
        return best if best_score >= 1 else None

    # Загружаем маппинги для поставщика (для кейсовок)
    mappings_by_name: dict[str, CoProductMapping] = {}
    mappings_by_code: dict[str, CoProductMapping] = {}
    if inv.supplier_id:
        for m in db.query(CoProductMapping).filter(CoProductMapping.supplier_id == inv.supplier_id).all():
            if m.supplier_product_name:
                mappings_by_name[m.supplier_product_name.strip().lower()] = m
            if m.supplier_product_code:
                mappings_by_code[m.supplier_product_code.strip().lower()] = m

    # Загружаем контейнеры
    container_ids = {m.container_id for m in list(mappings_by_name.values()) + list(mappings_by_code.values()) if m.container_id}
    containers: dict[int, CoProductContainer] = {}
    if container_ids:
        containers = {c.id: c for c in db.query(CoProductContainer).filter(CoProductContainer.id.in_(container_ids)).all()}

    # Формируем строки XML — точно как в reston invoices2
    items_xml_lines = []
    skipped = []
    for num, item in enumerate(inv.items, start=1):
        p = products.get(item.product_id) if item.product_id else None

        # Ищем маппинг для этой позиции (товар + кейсовка)
        name_key = (item.supplier_product_name or "").strip().lower()
        code_key = (item.supplier_product_code or "").strip().lower()
        mapping = mappings_by_name.get(name_key) or mappings_by_code.get(code_key)

        # Фолбэк 1: товар из маппинга (именно здесь зелёные позиции в UI)
        if (not p or not p.iiko_article_id) and mapping and mapping.product_id:
            p = db.query(CoProduct).filter(CoProduct.id == mapping.product_id, CoProduct.tenant_id == user.tenant_id).first()
        # Фолбэк 2: нечёткий поиск по названию
        if (not p or not p.iiko_article_id) and item.supplier_product_name:
            p = _fuzzy_find(item.supplier_product_name)
        if not p or not p.iiko_article_id:
            skipped.append(item.supplier_product_name or str(item.id))
            continue
        container = containers.get(mapping.container_id) if mapping and mapping.container_id else None

        qty = float(item.qty)
        price = float(item.price)
        total = round(qty * price, 2)

        # Если кейсовка: amount = qty * count, price = price / count
        if container:
            cnt = float(container.count)
            amount = qty * cnt
            unit_price = price / cnt if cnt else price
        else:
            amount = qty
            unit_price = price

        xml_item = [
            "    <item>",
            f"      <num>{num}</num>",
            f"      <product>{p.iiko_article_id}</product>",
            f"      <store>{warehouse.iiko_store_id}</store>",
            f"      <amount>{amount:.4f}</amount>",
            f"      <price>{unit_price:.4f}</price>",
            f"      <sum>{total:.2f}</sum>",
        ]
        if container:
            xml_item.append(f"      <containerId>{container.iiko_container_id}</containerId>")
        xml_item.append("    </item>")
        items_xml_lines += xml_item

    if not items_xml_lines:
        raise HTTPException(status_code=400, detail=f"Нет позиций с iiko маппингом. Пропущено: {', '.join(skipped[:5])}")

    # Входящий номер документа: из запроса → из БД (OCR) → fallback на ID
    if body.invoice_number:
        inv.document_number = body.invoice_number
    inv_number = inv.document_number or str(inv.id)

    xml_body = "\n".join([
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        "<document>",
        "  <items>",
        *items_xml_lines,
        "  </items>",
        f"  <dateIncoming>{body.date_incoming}</dateIncoming>",
        "  <useDefaultDocumentTime>true</useDefaultDocumentTime>",
        f"  <incomingDocumentNumber>{inv_number}</incomingDocumentNumber>",
        f"  <defaultStore>{warehouse.iiko_store_id}</defaultStore>",
        f"  <supplier>{supplier.iiko_id}</supplier>",
        "  <status>NEW</status>",
        "</document>",
    ])

    from app.api.co_admin import _iiko_session
    import requests as req
    import xml.etree.ElementTree as ET

    logger.info("CO post-to-iiko XML:\n%s", xml_body)

    key = _iiko_session(restaurant)
    resp = req.post(
        f"{restaurant.base_url}/resto/api/documents/import/incomingInvoice",
        params={"key": key},
        data=xml_body.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
        timeout=60,
    )

    logger.info("CO post-to-iiko response %s:\n%s", resp.status_code, resp.text[:1000])

    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"iiko HTTP {resp.status_code}: {resp.text[:400]}")

    root = ET.fromstring(resp.text)
    valid = (root.findtext("valid") or "").lower()
    error = root.findtext("errorMessage") or root.findtext("error") or ""

    if valid != "true":
        inv.status = "error"
        db.commit()
        raise HTTPException(status_code=400, detail=error or "iiko вернул ошибку без описания")

    inv.status = "sent"
    inv.needs_resend = False
    db.commit()

    return {
        "success": True,
        "documentNumber": root.findtext("documentNumber") or inv_number,
        "skipped": skipped,
    }
