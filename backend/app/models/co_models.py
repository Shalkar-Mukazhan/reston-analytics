"""SQLAlchemy models for coffee_original schema (separate client)."""
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, DateTime,
    Numeric, ForeignKey, Table, text, JSON,
)
from sqlalchemy.orm import relationship
from app.core.database import Base

_S = "coffee_original"


class CoRestaurant(Base):
    __tablename__ = "restaurants"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    code = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    base_url = Column(String(255), nullable=False)
    iiko_login = Column(String(100), nullable=False)
    iiko_password_hash = Column(String(255), nullable=False)
    iiko_concept_id = Column(String(100), nullable=True)
    inventory_preset_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")

    warehouses = relationship("CoWarehouse", back_populates="restaurant", cascade="all, delete-orphan")


class CoWarehouse(Base):
    __tablename__ = "restaurant_warehouses"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    iiko_store_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    is_writeoff_default = Column(Boolean, nullable=False, server_default="false")
    warehouse_type_id = Column(Integer, ForeignKey(f"{_S}.warehouse_types.id", ondelete="SET NULL"), nullable=True)

    restaurant = relationship("CoRestaurant", back_populates="warehouses")
    warehouse_type = relationship("CoWarehouseType", back_populates="warehouses")


class CoUser(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    email = Column(String(150), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, server_default="user")
    is_active = Column(Boolean, nullable=False, server_default="true")

    restaurants = relationship("CoRestaurant", secondary=f"{_S}.user_restaurants", lazy="joined")
    warehouses = relationship("CoWarehouse", secondary=f"{_S}.user_warehouses", lazy="joined")


class CoUserRestaurant(Base):
    __tablename__ = "user_restaurants"
    __table_args__ = {"schema": _S}

    user_id = Column(Integer, ForeignKey(f"{_S}.users.id", ondelete="CASCADE"), primary_key=True)
    restaurant_id = Column(Integer, ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"), primary_key=True)


class CoUserWarehouse(Base):
    __tablename__ = "user_warehouses"
    __table_args__ = {"schema": _S}

    user_id = Column(Integer, ForeignKey(f"{_S}.users.id", ondelete="CASCADE"), primary_key=True)
    warehouse_id = Column(Integer, ForeignKey(f"{_S}.restaurant_warehouses.id", ondelete="CASCADE"), primary_key=True)


class CoSupplier(Base):
    __tablename__ = "suppliers"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    iiko_id = Column(String(100), nullable=True, unique=True)
    name = Column(String(150), nullable=False)
    bin = Column(String(20), nullable=True)
    contact = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")


class CoProduct(Base):
    __tablename__ = "products"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    iiko_article_id = Column(String(100), nullable=True, unique=True)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")


class CoProductContainer(Base):
    __tablename__ = "product_containers"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey(f"{_S}.products.id", ondelete="CASCADE"), nullable=False)
    iiko_container_id = Column(String(100), nullable=False)
    name = Column(String(100), nullable=False)
    count = Column(Numeric(10, 3), nullable=False)

    product = relationship("CoProduct")


class CoProductMapping(Base):
    __tablename__ = "product_mapping"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    supplier_id = Column(Integer, ForeignKey(f"{_S}.suppliers.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey(f"{_S}.products.id", ondelete="SET NULL"), nullable=True)
    supplier_product_name = Column(String(255), nullable=False)
    supplier_product_code = Column(String(100), nullable=True)
    container_id = Column(Integer, ForeignKey(f"{_S}.product_containers.id", ondelete="SET NULL"), nullable=True)


class CoInvoice(Base):
    __tablename__ = "invoices"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey(f"{_S}.restaurant_warehouses.id", ondelete="RESTRICT"), nullable=False)
    supplier_id = Column(Integer, ForeignKey(f"{_S}.suppliers.id", ondelete="RESTRICT"), nullable=True)
    invoice_date = Column(Date, nullable=False)
    document_number = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False, server_default="draft")
    needs_resend = Column(Boolean, nullable=False, server_default="false")
    created_by = Column(Integer, ForeignKey(f"{_S}.users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)

    items = relationship("CoInvoiceItem", back_populates="invoice", cascade="all, delete-orphan")


class CoSetting(Base):
    __tablename__ = "co_settings"
    __table_args__ = {"schema": _S}

    key = Column(String(100), primary_key=True)
    value = Column(String, nullable=True)


class CoAccount(Base):
    __tablename__ = "co_accounts"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    account_iiko_id = Column(String(100), nullable=False, unique=True)
    name = Column(String(255), nullable=False)

    groups = relationship("CoProductGroup", back_populates="account")
    warehouse_types = relationship("CoWarehouseType", back_populates="account")


class CoWarehouseType(Base):
    __tablename__ = "warehouse_types"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    account_id = Column(Integer, ForeignKey(f"{_S}.co_accounts.id", ondelete="SET NULL"), nullable=True)

    account = relationship("CoAccount", back_populates="warehouse_types")
    warehouses = relationship("CoWarehouse", back_populates="warehouse_type")


class CoProductGroup(Base):
    __tablename__ = "co_product_groups"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    account_id = Column(Integer, ForeignKey(f"{_S}.co_accounts.id", ondelete="SET NULL"), nullable=True)

    account = relationship("CoAccount", back_populates="groups")
    members = relationship("CoProductGroupMember", back_populates="group", cascade="all, delete-orphan")


class CoProductGroupMember(Base):
    __tablename__ = "co_product_group_members"
    __table_args__ = {"schema": _S}

    group_id = Column(Integer, ForeignKey(f"{_S}.co_product_groups.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(Integer, ForeignKey(f"{_S}.products.id", ondelete="CASCADE"), primary_key=True)

    group = relationship("CoProductGroup", back_populates="members")
    product = relationship("CoProduct")


class CoWriteoffAct(Base):
    __tablename__ = "co_writeoff_acts"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"), nullable=False)
    warehouse_id = Column(Integer, ForeignKey(f"{_S}.restaurant_warehouses.id", ondelete="RESTRICT"), nullable=False)
    act_date = Column(Date, nullable=False)
    inventory_datetime = Column(DateTime(timezone=True), nullable=True)
    writeoff_datetime = Column(DateTime(timezone=True), nullable=True)
    total_sum = Column(Numeric(14, 2), nullable=True)
    comment = Column(String(500), nullable=True)
    status = Column(String(50), nullable=False, server_default="draft")
    iiko_doc_ids = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey(f"{_S}.users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"), nullable=False)
    posted_at = Column(DateTime(timezone=True), nullable=True)

    items = relationship("CoWriteoffItem", back_populates="act", cascade="all, delete-orphan")


class CoWriteoffItem(Base):
    __tablename__ = "co_writeoff_items"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    act_id = Column(Integer, ForeignKey(f"{_S}.co_writeoff_acts.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey(f"{_S}.products.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(12, 3), nullable=False)
    resigned_sum = Column(Numeric(14, 2), nullable=True)

    act = relationship("CoWriteoffAct", back_populates="items")
    product = relationship("CoProduct")


class CoInvoiceItem(Base):
    __tablename__ = "invoice_items"
    __table_args__ = {"schema": _S}

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey(f"{_S}.invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey(f"{_S}.products.id", ondelete="RESTRICT"), nullable=True)
    supplier_product_name = Column(String(255), nullable=True)
    supplier_product_code = Column(String(100), nullable=True)
    qty = Column(Numeric(12, 3), nullable=False)
    price = Column(Numeric(12, 2), nullable=False)

    invoice = relationship("CoInvoice", back_populates="items")
