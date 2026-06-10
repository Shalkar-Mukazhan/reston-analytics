"""Модели для OCR-накладных (Накладные 2) — отдельные таблицы."""
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class OcrInvoice(Base):
    """Накладная, распознанная через Claude Vision OCR."""
    __tablename__ = "ocr_invoices"

    id               = Column(Integer, primary_key=True, index=True)
    restaurant_id    = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    user_id          = Column(Integer, ForeignKey("users.id"), nullable=False)
    supplier_id       = Column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    supplier_name_raw = Column(String(255))          # как распознал OCR
    supplier_bin_iin  = Column(String(20),  nullable=True)  # ИНН/БИН из OCR
    invoice_number   = Column(String(100))
    invoice_date     = Column(DateTime(timezone=True))
    status           = Column(String(20), default="processed")  # processed | sent | error
    total_sum        = Column(Float)                 # итого без НДС
    total_sum_vat    = Column(Float)                 # итого с НДС
    error_message    = Column(String(1000))
    created_at       = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    restaurant = relationship("Restaurant")
    user       = relationship("User")
    supplier   = relationship("Supplier")
    items      = relationship("OcrInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class OcrInvoiceItem(Base):
    """Позиция OCR-накладной."""
    __tablename__ = "ocr_invoice_items"

    id             = Column(Integer, primary_key=True, index=True)
    invoice_id     = Column(Integer, ForeignKey("ocr_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    supplier_code  = Column(String(100))    # код поставщика (УТ-00001716)
    name           = Column(String(300), nullable=False)
    unit_type      = Column(String(20))
    quantity       = Column(Float)
    unit_price     = Column(Float)          # цена без НДС
    unit_price_vat = Column(Float)          # цена с НДС
    total_price    = Column(Float)          # сумма без НДС
    total_price_vat = Column(Float)         # сумма с НДС
    vat_amount     = Column(Float)          # сумма НДС

    iiko_product_id = Column(String(100))   # UUID товара в iiko (если сопоставлен)
    container_id    = Column(String(100))   # UUID фасовки в iiko (если кейсовая единица)

    invoice = relationship("OcrInvoice", back_populates="items")
