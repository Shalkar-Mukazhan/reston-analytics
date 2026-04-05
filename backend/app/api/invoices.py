"""
API накладных ABL.
POST /api/invoices/upload           — загрузить Excel накладную, распарсить, сохранить строки
GET  /api/invoices/                 — список накладных ресторана
GET  /api/invoices/{id}/items       — строки накладной
POST /api/invoices/{id}/post-to-iiko — отправить накладную в IIKO
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.catalog import Invoice, InvoiceItem, AblProduct, ProductCatalog, Supplier
from app.models.audit import AuditLog
from app.services.invoice_parser import parse_abl_invoice

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.post("/upload")
async def upload_invoice(
    restaurant_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Загрузка Excel-накладной от ABL.
    Парсим лист DETAILS, сопоставляем Subsys → abl_products → product_catalog.
    """
    # Проверяем доступ к ресторану
    restaurant = db.query(Restaurant).filter(Restaurant.id == restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if current_user.role not in ("admin", "co"):
        allowed_ids = [r.id for r in current_user.restaurants]
        if restaurant.id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Только Excel файлы (.xlsx, .xls)")

    # Читаем файл в память
    file_bytes = await file.read()

    # Парсим накладную
    try:
        rows, meta = parse_abl_invoice(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not rows:
        raise HTTPException(status_code=422, detail="Файл пустой или не содержит данных в листе DETAILS")

    # Определяем номер накладной из meta или из первой строки
    invoice_nums = list({r["invoice_num"] for r in rows if r["invoice_num"] != "nan"})
    primary_invoice_num = meta.get("invoice_number") or (invoice_nums[0] if invoice_nums else file.filename)

    # Кэш abl_products: abl_article → AblProduct
    all_abl_articles = {r["abl_article"] for r in rows}
    abl_map = {
        p.abl_article: p
        for p in db.query(AblProduct).filter(AblProduct.abl_article.in_(all_abl_articles)).all()
    }

    items = []
    not_found = []
    total_sum = 0.0
    total_sum_vat = 0.0

    for row in rows:
        abl_art  = row["abl_article"]
        abl_prod = abl_map.get(abl_art)

        if not abl_prod:
            not_found.append(abl_art)

        total_sum     += row["total_price"] or 0.0
        total_sum_vat += row["total_price_vat"] or 0.0

        item = InvoiceItem(
            invoice_id=0,          # временно, обновим после flush
            invoice_number=row["invoice_num"],
            abl_product_id=abl_prod.id if abl_prod else None,
            abl_article=abl_art,
            name=abl_prod.name if abl_prod else abl_art,
            quantity=row["quantity"],
            unit_price=row["unit_price"],
            unit_price_vat=row["unit_price_vat"],
            total_price=row["total_price"],
            total_price_vat=row["total_price_vat"],
        )
        items.append(item)

    # Автоматически привязываем поставщика ABL
    abl_supplier = db.query(Supplier).filter(Supplier.name.ilike("%ABL%")).first()

    # Создаём Invoice с уже посчитанными суммами
    invoice = Invoice(
        restaurant_id=restaurant.id,
        user_id=current_user.id,
        supplier_id=abl_supplier.id if abl_supplier else None,
        invoice_number=primary_invoice_num,
        invoice_date=meta.get("invoice_date"),
        status="processing",
        total_sum=round(total_sum, 2),
        total_sum_vat=round(total_sum_vat, 2),
    )
    db.add(invoice)
    db.flush()  # получаем invoice.id

    for item in items:
        item.invoice_id = invoice.id

    db.bulk_save_objects(items)

    invoice.status = "processed"
    if not_found:
        invoice.error_message = f"Не найдены в справочнике: {', '.join(not_found[:10])}"

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="upload_invoice",
        details=f"file={file.filename}, rows={len(items)}, not_found={len(not_found)}",
    ))
    db.commit()

    return {
        "invoice_id": invoice.id,
        "invoice_number": primary_invoice_num,
        "status": invoice.status,
        "items_count": len(items),
        "total_rows": len(items),
        "total_sum": invoice.total_sum,
        "total_sum_vat": invoice.total_sum_vat,
        "matched": len(items) - len(not_found),
        "not_found_count": len(not_found),
        "not_found": not_found[:20],
    }


@router.get("/")
def list_invoices(
    restaurant_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Invoice)
    if current_user.role not in ("admin", "co"):
        allowed_ids = [r.id for r in current_user.restaurants]
        query = query.filter(Invoice.restaurant_id.in_(allowed_ids))
    elif restaurant_id:
        query = query.filter(Invoice.restaurant_id == restaurant_id)

    invoices = query.order_by(Invoice.created_at.desc()).limit(100).all()
    return [
        {
            "id": inv.id,
            "restaurant_id": inv.restaurant_id,
            "invoice_number": inv.invoice_number,
            "filename": inv.invoice_number,
            "invoice_date": inv.invoice_date,
            "status": inv.status,
            "error_message": inv.error_message,
            "uploaded_at": inv.created_at,
            "created_at": inv.created_at,
            "total_sum": inv.total_sum,
            "total_sum_vat": inv.total_sum_vat,
            "supplier_name": inv.supplier.name if inv.supplier else None,
            "items_count": len(inv.items),
        }
        for inv in invoices
    ]


class PostToIikoRequest(BaseModel):
    date_incoming: str   # "dd.MM.yyyy"
    time_incoming: str = "00:00"  # "HH:mm"


@router.post("/{invoice_id}/post-to-iiko")
def post_invoice_to_iiko(
    invoice_id: int,
    body: PostToIikoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Отправляет накладную ABL в IIKO через incomingInvoice XML API."""
    from app.services.iiko import post_invoice

    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    restaurant = db.query(Restaurant).filter(Restaurant.id == invoice.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if not restaurant.store_id:
        raise HTTPException(status_code=400, detail="У ресторана не задан storeId. Выполните синхронизацию складов в Admin.")

    # Поставщик
    supplier = db.query(Supplier).filter(Supplier.id == invoice.supplier_id).first()
    if not supplier:
        raise HTTPException(status_code=400, detail="Поставщик не привязан к накладной. Выполните sync-suppliers в Admin.")

    # Строки накладной с привязкой к IIKO товару
    rows = (
        db.query(InvoiceItem, AblProduct, ProductCatalog)
        .outerjoin(AblProduct, InvoiceItem.abl_product_id == AblProduct.id)
        .outerjoin(ProductCatalog, AblProduct.product_catalog_id == ProductCatalog.id)
        .filter(InvoiceItem.invoice_id == invoice_id)
        .all()
    )

    # Номер накладной из HEADER (№ накладной) — один для всего документа
    doc_invoice_number = invoice.invoice_number

    items_list_all = []
    skipped = []

    for item, abl, prod in rows:
        if not prod or not prod.product_iiko_id:
            skipped.append(item.abl_article)
            continue

        # vat_pct из unit_price и unit_price_vat
        if item.unit_price and item.unit_price > 0 and item.unit_price_vat:
            vat_pct = round((item.unit_price_vat / item.unit_price - 1) * 100)
        else:
            vat_pct = 0

        vat_sum = round((item.total_price_vat or 0) - (item.total_price or 0), 2)

        items_list_all.append({
            "product_id": prod.product_iiko_id,
            "amount": item.quantity or 0,
            "price": item.unit_price_vat or 0,
            "sum": item.total_price_vat or 0,
            "vat_pct": vat_pct,
            "vat_sum": vat_sum,
        })

    if not items_list_all:
        raise HTTPException(status_code=400, detail=f"Нет товаров с product_iiko_id. Не найдено в IIKO: {', '.join(skipped[:10])}")

    results = []
    errors = []

    # Один XML документ на всю накладную
    if True:
        inv_num = doc_invoice_number
        xml_lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<document>", "  <items>"]
        for i, it in enumerate(items_list_all, start=1):
            xml_lines += [
                "    <item>",
                f"      <num>{i}</num>",
                f"      <product>{it['product_id']}</product>",
                f"      <store>{restaurant.store_id}</store>",
                f"      <amount>{it['amount']:.4f}</amount>",
                f"      <price>{it['price']:.2f}</price>",
                f"      <sum>{it['sum']:.2f}</sum>",
                f"      <vatPercent>{it['vat_pct']:.0f}</vatPercent>",
                f"      <vatSum>{it['vat_sum']:.2f}</vatSum>",
                "    </item>",
            ]
        xml_lines += [
            "  </items>",
            f"  <dateIncoming>{body.date_incoming}</dateIncoming>",
            f"  <invoice>{inv_num}</invoice>",
            f"  <defaultStore>{restaurant.store_id}</defaultStore>",
            f"  <supplier>{supplier.iiko_uuid}</supplier>",
            "  <status>NEW</status>",
            "</document>",
        ]
        xml_body = "\n".join(xml_lines)

        try:
            result = post_invoice(db, restaurant, xml_body)
            if result.get("valid", "").lower() == "true":
                results.append({"invoice_num": inv_num, "documentNumber": result.get("documentNumber", "")})
            else:
                err = result.get("error") or result.get("warning") or "неизвестная ошибка"
                errors.append({"invoice_num": inv_num, "error": err})
        except Exception as e:
            errors.append({"invoice_num": inv_num, "error": str(e)})

    # Обновляем статус накладной
    if errors and not results:
        invoice.status = "error"
        invoice.error_message = errors[0]["error"][:500]
    else:
        invoice.status = "sent"

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="post_invoice_to_iiko",
        details=f"invoice_id={invoice_id}, sent={len(results)}, errors={len(errors)}",
    ))
    db.commit()

    return {
        "sent": len(results),
        "errors": errors,
        "skipped": skipped[:10],
        "results": results,
    }


@router.get("/{invoice_id}/items")
def invoice_items(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Накладная не найдена")

    items = (
        db.query(InvoiceItem, AblProduct, ProductCatalog)
        .outerjoin(AblProduct, InvoiceItem.abl_product_id == AblProduct.id)
        .outerjoin(ProductCatalog, AblProduct.product_catalog_id == ProductCatalog.id)
        .filter(InvoiceItem.invoice_id == invoice_id)
        .all()
    )

    return [
        {
            "id": item.id,
            "invoice_number": item.invoice_number,
            "abl_article": item.abl_article,
            "name": item.name,
            "iiko_product_id": prod.product_iiko_id if prod else None,
            "iiko_product_name": prod.name if prod else None,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "unit_price_vat": item.unit_price_vat,
            "total_price": item.total_price,
            "total_price_vat": item.total_price_vat,
            "matched": prod is not None and prod.product_iiko_id is not None,
        }
        for item, abl, prod in items
    ]
