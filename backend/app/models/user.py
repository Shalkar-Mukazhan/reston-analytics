from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Table, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

# Связь многие-ко-многим: пользователь ↔ ресторан
user_restaurants = Table(
    "user_restaurants",
    Base.metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("restaurant_id", ForeignKey("restaurants.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="store")  # "store" | "co"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    restaurants = relationship("Restaurant", secondary=user_restaurants, back_populates="users")
    audit_logs = relationship("AuditLog", back_populates="user")
