from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Table, UniqueConstraint, Date
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.user import user_restaurants

# Связь many-to-many: ресторан ↔ пресет
restaurant_presets = Table(
    "restaurant_presets",
    Base.metadata,
    Column("restaurant_id", ForeignKey("restaurants.id"), primary_key=True),
    Column("preset_id", ForeignKey("preset_definitions.id"), primary_key=True),
)


class PresetDefinition(Base):
    """Уникальные пресеты IIKO — UUID хранится один раз"""
    __tablename__ = "preset_definitions"

    id = Column(Integer, primary_key=True, index=True)
    preset_type = Column(String(100), nullable=False)   # sales, writeoff, inventory... или произвольный
    preset_uuid = Column(String(100), nullable=False)
    description = Column(String(255))

    __table_args__ = (
        UniqueConstraint("preset_type", "preset_uuid", name="uq_preset_definition"),
    )

    restaurants = relationship("Restaurant", secondary=restaurant_presets, back_populates="presets")


class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    department_name = Column(String(100))
    base_url = Column(String(255), nullable=False)
    iiko_login = Column(String(100), nullable=False)
    iiko_password_hash = Column(String(255), nullable=False)
    store_id = Column(String(100), nullable=True)   # UUID склада IIKO для отправки накладных
    is_active = Column(Boolean, default=True)

    # Feature flags — управляются из Admin > Доступ (только ЦО)
    feat_invoices  = Column(Boolean, nullable=False, default=True)
    feat_analytics = Column(Boolean, nullable=False, default=True)
    feat_reports   = Column(Boolean, nullable=False, default=True)
    feat_planning  = Column(Boolean, nullable=False, default=True)
    feat_checklist = Column(Boolean, nullable=False, default=True)

    # Google Sheets — ссылка на таблицу ресторана (iiko_sync.py)
    google_sheet_url = Column(String(500), nullable=True)

    # Чек-лист: управление рабочим днём
    checklist_start_hour = Column(Integer, nullable=False, default=7)   # час начала бизнес-дня
    last_checklist_reset_date = Column(Date, nullable=True)             # дата последнего нажатия кнопки

    users = relationship("User", secondary=user_restaurants, back_populates="restaurants")
    reports = relationship("Report", back_populates="restaurant")
    metrics = relationship("WasteMetric", back_populates="restaurant")
    iiko_sessions = relationship("IikoSession", back_populates="restaurant")
    presets = relationship("PresetDefinition", secondary=restaurant_presets, back_populates="restaurants")

    def get_preset(self, preset_type: str) -> str | None:
        """Удобный метод: restaurant.get_preset('sales') → UUID"""
        for p in self.presets:
            if p.preset_type == preset_type:
                return p.preset_uuid
        return None
