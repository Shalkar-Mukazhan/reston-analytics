from sqlalchemy import Boolean, Column, Integer, String, Date, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class SalesMonthlyTarget(Base):
    __tablename__ = "sales_monthly_targets"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    month = Column(String(7), nullable=False)       # YYYY-MM
    gc_target = Column(Integer, nullable=True)
    sales_target = Column(Numeric(14, 2), nullable=True)
    set_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SalesDailyFact(Base):
    __tablename__ = "sales_daily_facts"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    gc_fact = Column(Integer, nullable=True)
    sales_fact = Column(Numeric(14, 2), nullable=True)
    av_check_fact = Column(Numeric(10, 2), nullable=True)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())


class SalesDailyPlan(Base):
    __tablename__ = "sales_daily_plans"

    id = Column(Integer, primary_key=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    gc_plan = Column(Integer, nullable=True)
    sales_plan = Column(Numeric(14, 2), nullable=True)
    av_check_plan = Column(Numeric(10, 2), nullable=True)
    is_manual = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
