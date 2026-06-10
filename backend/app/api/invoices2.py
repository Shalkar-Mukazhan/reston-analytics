"""
Накладные 2 — OCR через Claude Vision.

POST /api/invoices2/ocr-parse     — распознать фото/PDF, вернуть JSON (без сохранения)
POST /api/invoices2/ocr-confirm   — сохранить подтверждённую накладную в БД
GET  /api/invoices2/              — список накладных
GET  /api/invoices2/{id}/items    — позиции накладной
POST /api/invoices2/{id}/post-to-iiko — отправить в iiko
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.audit import AuditLog
from app.models.catalog import Supplier, SupplierProductMapping, AblProduct, ProductCatalog
from app.models.restaurant import Restaurant
from app.models.user import User
from app.models.ocr_invoice import OcrInvoice, OcrInvoiceItem

router = APIRouter(prefix="/api/invoices2", tags=["invoices2"])

# Единицы измерения, которые означают кейс/упаковку
_CASE_UNITS = {"кор", "кор.", "коробка", "коробок", "уп", "уп.", "упак", "упаковка", "бл", "блок", "ящ", "ящик"}

def _pick_container(unit_type: str | None, containers: list | None) -> str | None:
    """Возвращает container_id если единица кейсовая и есть подходящий контейнер.
    Если кор. но контейнеров нет — возвращает None (базовая единица).
    При нескольких кейсах — берём с наибольшим count.
    """
    if not unit_type or not containers:
        return None
    if unit_type.lower().strip() not in _CASE_UNITS:
        return None
    # Только кейсовые контейнеры (count > 1)
    case_containers = [c for c in containers if c.get("count", 1) > 1]
    if not case_containers:
        return None  # кор. но нет кейса — используем базовую единицу
    # Берём с наибольшим count
    best = max(case_containers, key=lambda c: c.get("count", 1))
    return best["id"]

# ── Медиатипы ─────────────────────────────────────────────────────────────────

_MEDIA_TYPES = {
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".webp": "image/webp",
    ".pdf":  "application/pdf",
}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 МБ


def _detect_media_type(filename: str) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    mt = _MEDIA_TYPES.get(ext)
    if not mt:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются форматы: JPEG, PNG, WebP, PDF",
        )
    return mt


# ── OCR parse (только распознавание, без сохранения) ─────────────────────────

@router.post("/ocr-parse")
async def ocr_parse(
    restaurant_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Распознаёт 1–5 фото/PDF накладной через Claude Vision. Ничего не сохраняет."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    if current_user.role not in ("admin", "co"):
        if restaurant.id not in [r.id for r in current_user.restaurants]:
            raise HTTPException(status_code=403, detail="Нет доступа к ресторану")

    if not files:
        raise HTTPException(status_code=400, detail="Нет файлов")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Максимум 5 файлов за раз")

    parsed_files: list[tuple[bytes, str]] = []
    for upload in files:
        media_type = _detect_media_type(upload.filename or "file.jpg")
        file_bytes = await upload.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"Файл {upload.filename!r} слишком большой (максимум 5 МБ)",
            )
        parsed_files.append((file_bytes, media_type))

    try:
        from app.services.ocr_service import parse_invoice_ocr
        result = parse_invoice_ocr(parsed_files)
    except RuntimeError as e:
        logger.error("OCR RuntimeError: %s", e)
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("OCR unexpected error, files=%d", len(parsed_files))
        raise HTTPException(status_code=422, detail=f"Ошибка распознавания: {e}")

    return result


# ── OCR confirm (сохранение подтверждённых данных) ────────────────────────────

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
    document_number: str | None = None
    document_date: str | None = None
    supplier_name: str | None = None
    supplier_bin_iin: str | None = None
    items: list[OcrItemIn]
    total_sum_with_vat: float | None = None


@router.post("/ocr-confirm")
def ocr_confirm(
    body: OcrConfirmRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Сохраняет накладную, подтверждённую оператором после OCR."""
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")
    if current_user.role not in ("admin", "co"):
        if restaurant.id not in [r.id for r in current_user.restaurants]:
            raise HTTPException(status_code=403, detail="Нет доступа к ресторану")

    # Дата
    invoice_date = None
    if body.document_date:
        for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
            try:
                invoice_date = datetime.strptime(body.document_date, fmt)
                break
            except ValueError:
                pass

    # Поставщик: сначала по БИН/ИИН (точный), потом по имени (нечёткий)
    supplier = None
    if body.supplier_bin_iin:
        supplier = db.query(Supplier).filter(
            Supplier.taxpayer_id == body.supplier_bin_iin.strip()
        ).first()
    if not supplier and body.supplier_name:
        keyword = body.supplier_name[:30]
        supplier = db.query(Supplier).filter(
            Supplier.name.ilike(f"%{keyword}%")
        ).first()

    # Суммы
    total_vat = sum(i.total_with_vat for i in body.items)
    total_no_vat = sum(
        i.total_with_vat - (i.vat_amount or 0) for i in body.items
    )

    # Авто-маппинг товаров через прайс-лист поставщика
    pricelist_map: dict[str, str] = {}  # supplier_code → iiko_product_id
    if supplier:
        rows = db.query(SupplierProductMapping).filter(
            SupplierProductMapping.supplier_id == supplier.id
        ).all()
        pricelist_map = {r.supplier_product_code: r.iiko_product_id for r in rows if r.supplier_product_code}

    invoice = OcrInvoice(
        restaurant_id=restaurant.id,
        user_id=current_user.id,
        supplier_id=supplier.id if supplier else None,
        supplier_name_raw=body.supplier_name,
        supplier_bin_iin=body.supplier_bin_iin,
        invoice_number=body.document_number or "OCR",
        invoice_date=invoice_date,
        status="processed",
        total_sum=round(total_no_vat, 2),
        total_sum_vat=round(total_vat, 2),
    )
    db.add(invoice)
    db.flush()

    items_to_save = []
    for row in body.items:
        vat_amt = row.vat_amount or 0
        total_no = row.total_with_vat - vat_amt
        unit_price_no_vat = round(total_no / row.quantity, 4) if row.quantity else 0

        iiko_id = pricelist_map.get(row.supplier_code or "") or None

        items_to_save.append(OcrInvoiceItem(
            invoice_id=invoice.id,
            supplier_code=row.supplier_code or "",
            name=row.name,
            unit_type=row.unit or "шт",
            quantity=row.quantity,
            unit_price=unit_price_no_vat,
            unit_price_vat=row.price_per_unit,
            total_price=round(total_no, 2),
            total_price_vat=row.total_with_vat,
            vat_amount=vat_amt,
            iiko_product_id=iiko_id,
        ))

    db.bulk_save_objects(items_to_save)

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="upload_invoice_ocr",
        details=f"doc={body.document_number}, rows={len(items_to_save)}",
    ))
    db.commit()

    matched_count = sum(1 for i in items_to_save if i.iiko_product_id)
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "items_count": len(items_to_save),
        "iiko_matched": matched_count,
        "iiko_unmatched": len(items_to_save) - matched_count,
        "supplier_matched": supplier.name if supplier else None,
        "total_sum_vat": invoice.total_sum_vat,
    }


# ── Список накладных ──────────────────────────────────────────────────────────

@router.get("/")
def list_invoices(
    restaurant_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(OcrInvoice)
    if current_user.role not in ("admin", "co"):
        allowed = [r.id for r in current_user.restaurants]
        query = query.filter(OcrInvoice.restaurant_id.in_(allowed))
    elif restaurant_id:
        query = query.filter(OcrInvoice.restaurant_id == restaurant_id)

    invoices = query.order_by(OcrInvoice.created_at.desc()).limit(100).all()
    return [
        {
            "id": inv.id,
            "restaurant_id": inv.restaurant_id,
            "invoice_number": inv.invoice_number,
            "invoice_date": inv.invoice_date,
            "status": inv.status,
            "error_message": inv.error_message,
            "uploaded_at": inv.created_at,
            "total_sum": inv.total_sum,
            "total_sum_vat": inv.total_sum_vat,
            "supplier_name": inv.supplier.name if inv.supplier else inv.supplier_name_raw,
            "items_count": len(inv.items),
        }
        for inv in invoices
    ]


# ── Позиции накладной ─────────────────────────────────────────────────────────

@router.get("/{invoice_id}/items")
def invoice_items(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(OcrInvoice).filter(OcrInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    return [
        {
            "id": item.id,
            "supplier_code": item.supplier_code,
            "name": item.name,
            "unit_type": item.unit_type,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "unit_price_vat": item.unit_price_vat,
            "total_price": item.total_price,
            "total_price_vat": item.total_price_vat,
            "vat_amount": item.vat_amount,
            "iiko_product_id": item.iiko_product_id,
            "matched": bool(item.iiko_product_id),
        }
        for item in invoice.items
    ]


# ── Отправка в iiko ───────────────────────────────────────────────────────────

class PostToIikoRequest(BaseModel):
    date_incoming: str  # "dd.MM.yyyy"


@router.post("/{invoice_id}/post-to-iiko")
def post_to_iiko(
    invoice_id: int,
    body: PostToIikoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.iiko import post_invoice

    invoice = db.query(OcrInvoice).filter(OcrInvoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
    if not restaurant or not restaurant.store_id:
        raise HTTPException(
            status_code=400,
            detail="У ресторана не задан storeId. Выполните синхронизацию складов в Admin.",
        )

    # Ищем поставщика: по supplier_id → по БИН/ИИН → по имени
    supplier = None
    if invoice.supplier_id:
        supplier = db.query(Supplier).filter(Supplier.id == invoice.supplier_id).first()
    if not supplier and invoice.supplier_bin_iin:
        supplier = db.query(Supplier).filter(
            Supplier.taxpayer_id == invoice.supplier_bin_iin.strip()
        ).first()
    if not supplier and invoice.supplier_name_raw:
        supplier = db.query(Supplier).filter(
            Supplier.name.ilike(f"%{invoice.supplier_name_raw[:25]}%")
        ).first()

    if not supplier:
        raise HTTPException(
            status_code=400,
            detail=f"Поставщик не найден (БИН: {invoice.supplier_bin_iin}, имя: {invoice.supplier_name_raw}). "
                   "Добавьте ИНН поставщику в iiko и выполните «Синхронизация поставщиков» в Admin.",
        )

    # Если supplier_id не был сохранён — обновляем сейчас
    if not invoice.supplier_id:
        invoice.supplier_id = supplier.id

    # Если у позиций нет iiko_product_id — пробуем подтянуть из прайс-листа
    unmapped = [i for i in invoice.items if not i.iiko_product_id]
    if unmapped:
        pricelist = {
            m.supplier_product_code: m.iiko_product_id
            for m in db.query(SupplierProductMapping).filter(
                SupplierProductMapping.supplier_id == supplier.id
            ).all()
            if m.supplier_product_code
        }
        # Фолбэк: ABL артикул → ProductCatalog → product_iiko_id
        abl_products = {
            a.abl_article: a
            for a in db.query(AblProduct).filter(AblProduct.product_catalog_id.isnot(None)).all()
            if a.product and a.product.product_iiko_id
        }
        for item in unmapped:
            if item.supplier_code:
                if item.supplier_code in pricelist:
                    item.iiko_product_id = pricelist[item.supplier_code]
                elif item.supplier_code in abl_products:
                    abl = abl_products[item.supplier_code]
                    item.iiko_product_id = abl.product.product_iiko_id
                    item.container_id = _pick_container(item.unit_type, abl.product.containers)

    # Для уже привязанных — тоже проставим container_id если нет
    for item in invoice.items:
        if item.iiko_product_id and not item.container_id:
            cat = db.query(ProductCatalog).filter(
                ProductCatalog.product_iiko_id == item.iiko_product_id
            ).first()
            if cat:
                item.container_id = _pick_container(item.unit_type, cat.containers)

    items = [i for i in invoice.items if i.iiko_product_id]
    skipped = [i.supplier_code or i.name for i in invoice.items if not i.iiko_product_id]

    if not items:
        raise HTTPException(
            status_code=400,
            detail=f"Нет позиций сопоставленных с iiko. Выполните «Синхронизация прайс-листов» в Admin. "
                   f"Коды поставщика: {', '.join(skipped[:5])}",
        )

    # Предвычислим count контейнеров: когда задан containerId, IIKO ожидает
    # amount и price в базовых единицах (amount = qty × count, price = price / count).
    container_counts: dict[str, int] = {}  # container_id → count
    product_ids_with_container = {i.iiko_product_id for i in items if i.container_id}
    if product_ids_with_container:
        cats = db.query(ProductCatalog).filter(
            ProductCatalog.product_iiko_id.in_(product_ids_with_container)
        ).all()
        for cat in cats:
            if cat.containers:
                for c in cat.containers:
                    container_counts[c["id"]] = c.get("count", 1)

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        "<document>",
        "  <items>",
    ]
    for i, item in enumerate(items, start=1):
        cnt = container_counts.get(item.container_id, 1) if item.container_id else 1
        amount = item.quantity * cnt
        price = item.unit_price_vat / cnt if cnt > 1 else item.unit_price_vat
        item_xml = [
            "    <item>",
            f"      <num>{i}</num>",
            f"      <product>{item.iiko_product_id}</product>",
            f"      <store>{restaurant.store_id}</store>",
            f"      <amount>{amount:.4f}</amount>",
            f"      <price>{price:.4f}</price>",
            f"      <sum>{item.total_price_vat:.2f}</sum>",
        ]
        if item.container_id:
            item_xml.append(f"      <containerId>{item.container_id}</containerId>")
        item_xml.append("    </item>")
        xml_lines += item_xml
    xml_lines += [
        "  </items>",
        f"  <dateIncoming>{body.date_incoming}</dateIncoming>",
        "  <useDefaultDocumentTime>true</useDefaultDocumentTime>",
        f"  <invoice>{invoice.invoice_number}</invoice>",
        f"  <defaultStore>{restaurant.store_id}</defaultStore>",
        f"  <supplier>{supplier.iiko_uuid}</supplier>",
        "  <status>NEW</status>",
        "</document>",
    ]

    try:
        result = post_invoice(db, restaurant, "\n".join(xml_lines))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result.get("valid", "").lower() == "true":
        invoice.status = "sent"
        db.add(AuditLog(
            user_id=current_user.id,
            restaurant_id=restaurant.id,
            action="post_invoice2_to_iiko",
            details=f"invoice_id={invoice_id}, doc={result.get('documentNumber')}",
        ))
        db.commit()
        return {
            "success": True,
            "documentNumber": result.get("documentNumber", ""),
            "skipped": skipped,
        }
    else:
        err = result.get("error") or result.get("warning") or "Неизвестная ошибка iiko"
        invoice.status = "error"
        invoice.error_message = err[:500]
        db.commit()
        raise HTTPException(status_code=400, detail=err)
