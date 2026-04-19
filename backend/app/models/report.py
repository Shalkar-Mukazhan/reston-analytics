from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    period = Column(String(20), nullable=False)       # "2024-03" или "2024-03-W1"
    period_type = Column(String(10), default="month") # "month" | "week"
    status = Column(String(20), default="pending")    # "pending" | "ready" | "error"
    error_message = Column(String(1000))
    date_from = Column(DateTime(timezone=True))
    date_to = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    restaurant = relationship("Restaurant", back_populates="reports")
    user = relationship("User")
    items = relationship("ReportItem", back_populates="report", cascade="all, delete-orphan")


class ReportItem(Base):
    __tablename__ = "report_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("product_catalog.id"), nullable=True)
    product_num = Column(String(100), nullable=True)   # код товара из IIKO (Product.Num)
    product_name = Column(String(500), nullable=True)  # название из product_catalog

    # Данные из IIKO
    sales_qty = Column(Float, default=0.0)
    sales_sum = Column(Float, default=0.0)
    writeoff_qty = Column(Float, default=0.0)
    writeoff_sum = Column(Float, default=0.0)
    inventory_qty = Column(Float, default=0.0)
    inventory_sum = Column(Float, default=0.0)

    # Расчётные поля
    allowed_qty = Column(Float, default=0.0)
    to_writeoff_qty = Column(Float, default=0.0)
    written_off_pct = Column(Float, default=0.0)

    # Статус строки
    is_over_limit = Column(Boolean, default=False)
    status = Column(String(20), default="ok", index=True)
    # ok | over_limit | no_category | no_rate | no_writeoff_needed | needs_check
    comment = Column(String(500))

    report = relationship("Report", back_populates="items")
    product = relationship("ProductCatalog")


class WasteMetric(Base):
    __tablename__ = "waste_metrics"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    report_id = Column(Integer, ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    period = Column(String(20), nullable=False)
    revenue_sum = Column(Float, default=0.0)
    shortage_sum = Column(Float, default=0.0)
    complete_waste_sum = Column(Float, default=0.0)
    shortage_pct = Column(Float, default=0.0)
    writeoff_pct = Column(Float, default=0.0)
    waste_pct = Column(Float, default=0.0)       # shortage + writeoff combined
    to_writeoff_qty = Column(Float, default=0.0) # позиций к списанию
    over_limit_count = Column(Integer, default=0)
    created_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                         onupdate=lambda: datetime.now(timezone.utc))

    restaurant = relationship("Restaurant", back_populates="metrics")


class IikoSession(Base):
    __tablename__ = "iiko_sessions"

    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False)
    session_key = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    restaurant = relationship("Restaurant", back_populates="iiko_sessions")
