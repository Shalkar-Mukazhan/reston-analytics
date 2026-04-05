from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class AblProduct(Base):
    """Маппинг артикулов ABL (поставщик) → товары IIKO (product_catalog)"""
    __tablename__ = "abl_products"

    id                = Column(Integer, primary_key=True, index=True)
    abl_article       = Column(String(50),  unique=True, nullable=False, index=True)
    abl_main_article  = Column(String(50),  nullable=False, index=True)
    name              = Column(String(300), nullable=False)
    supplier          = Column(String(255))
    price             = Column(Float)       # без НДС
    price_vat         = Column(Float)       # с НДС
    product_catalog_id = Column(Integer, ForeignKey("product_catalog.id", ondelete="SET NULL"), nullable=True, index=True)

    product = relationship("ProductCatalog")
    invoice_items = relationship("InvoiceItem", back_populates="abl_product")


class Account(Base):
    """Счета списания IIKO — куда списывать каждую группу товаров"""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_iiko_id = Column(String(100), unique=True, nullable=False)
    name = Column(String(255), nullable=False)

    groups = relationship("ProductGroup", back_populates="account")


class ProductGroup(Base):
    """Группы товаров — Булки, Пирожки, Продукты Кафе..."""
    __tablename__ = "product_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

    account = relationship("Account", back_populates="groups")
    products = relationship("ProductCatalog", back_populates="group")
    waste_rates = relationship("WasteRate", back_populates="group")


class ProductCatalog(Base):
    """Справочник товаров — перенесён из refs_goods.xlsx"""
    __tablename__ = "product_catalog"

    id = Column(Integer, primary_key=True, index=True)
    product_iiko_id = Column(String(100), unique=True, nullable=False, index=True)
    product_num = Column(String(50), nullable=False, index=True)   # IIKO code (числовой)
    product_article = Column(String(100), nullable=True, index=True)  # IIKO num/артикул — именно это OLAP возвращает в Product.Num
    name = Column(String(255), nullable=False)
    group_id   = Column(Integer, ForeignKey("product_groups.id"), nullable=True)
    unit_type  = Column(String(100))
    is_deleted = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime(timezone=True))

    group = relationship("ProductGroup", back_populates="products")


class WasteRate(Base):
    """Нормы списания по группам для каждого ресторана"""
    __tablename__ = "waste_rates"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("product_groups.id"), nullable=False)
    rate_pct = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint("restaurant_id", "group_id", name="uq_waste_rate"),
    )

    restaurant = relationship("Restaurant")
    group = relationship("ProductGroup", back_populates="waste_rates")


class Supplier(Base):
    """Поставщики из IIKO — нужны для отправки накладных"""
    __tablename__ = "suppliers"

    id        = Column(Integer, primary_key=True, index=True)
    iiko_uuid = Column(String(100), unique=True, nullable=False, index=True)
    name      = Column(String(255), nullable=False)

    invoices = relationship("Invoice", back_populates="supplier")


class Invoice(Base):
    """Накладные ABL"""
    __tablename__ = "invoices"

    id             = Column(Integer, primary_key=True, index=True)
    restaurant_id  = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    supplier_id    = Column(Integer, ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    invoice_number = Column(String(100))
    invoice_date   = Column(DateTime(timezone=True))
    status         = Column(String(20), default="processing")  # processing | processed | error
    total_sum      = Column(Float)      # итого без НДС
    total_sum_vat  = Column(Float)      # итого с НДС
    error_message  = Column(String(1000))
    created_at     = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    restaurant = relationship("Restaurant")
    user       = relationship("User")
    supplier   = relationship("Supplier", back_populates="invoices")
    items      = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceItem(Base):
    """Строки накладной ABL — сохраняются при загрузке файла"""
    __tablename__ = "invoice_items"

    id               = Column(Integer, primary_key=True, index=True)
    invoice_id       = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    abl_product_id   = Column(Integer, ForeignKey("abl_products.id", ondelete="SET NULL"), nullable=True, index=True)

    # Сырые данные из накладной
    invoice_number   = Column(String(100))   # номер счёта-фактуры из файла
    abl_article      = Column(String(50))    # артикул как в файле
    name             = Column(String(300))   # наименование из файла
    quantity         = Column(Float)
    unit_type        = Column(String(20))
    unit_price       = Column(Float)         # цена без НДС
    unit_price_vat   = Column(Float)         # цена с НДС
    total_price      = Column(Float)         # сумма без НДС
    total_price_vat  = Column(Float)         # сумма с НДС

    invoice     = relationship("Invoice", back_populates="items")
    abl_product = relationship("AblProduct", back_populates="invoice_items")
