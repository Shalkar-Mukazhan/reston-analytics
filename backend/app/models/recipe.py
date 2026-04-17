from sqlalchemy import (
    Column, Integer, String, Float, Date, Boolean,
    DateTime, ForeignKey, UniqueConstraint, Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.core.database import Base


class RecipeChangeLog(Base):
    """
    Лог bulk-изменений техкарт. Хранит снапшот ингредиентов до изменения
    для возможности отката.
    """
    __tablename__ = "recipe_change_logs"

    id            = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    operation_type = Column(String(50), nullable=False)  # bulk_remove / bulk_replace / bulk_update_amount / import_excel
    performed_at  = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    performed_by  = Column(String(100), nullable=True)   # username
    effective_date = Column(Date, nullable=False)         # дата с которой вступило в силу
    description   = Column(Text, nullable=True)           # человекочитаемое описание изменения
    # JSON: [{dish_name, chart_id, iiko_uuid, ingredients: [{ingredient_name, ingredient_iiko_uuid, amount_in, amount_middle, amount_out}]}]
    snapshot      = Column(Text, nullable=False)
    is_rolled_back = Column(Boolean, default=False, nullable=False)

    restaurant = relationship("Restaurant")


class Dish(Base):
    """
    Блюда, модификаторы и заготовки из IIKO (номенклатура с техкартами).
    Отличаются от product_catalog — это готовые блюда, а не сырьё.
    """
    __tablename__ = "dishes"

    id            = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    iiko_uuid     = Column(String(100), nullable=False, index=True)  # assembledProductId
    name          = Column(String(500), nullable=True)               # название блюда из IIKO
    synced_at     = Column(DateTime(timezone=True))

    __table_args__ = (
        UniqueConstraint("restaurant_id", "iiko_uuid", name="uq_dish_restaurant"),
    )

    restaurant = relationship("Restaurant")
    charts     = relationship("AssemblyChart", back_populates="dish", cascade="all, delete-orphan")


class AssemblyChart(Base):
    """
    Технологическая карта (рецепт) — привязана к блюду и периоду действия.
    Одно блюдо может иметь несколько техкарт (разные периоды).
    Размеры блюд (SPECIFIC) не используем — всегда COMMON.
    """
    __tablename__ = "assembly_charts"

    id            = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey("restaurants.id"), nullable=False, index=True)
    iiko_uuid     = Column(String(100), nullable=False, index=True)  # id из API
    dish_id       = Column(Integer, ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False, index=True)

    date_from         = Column(Date, nullable=False)
    date_to           = Column(Date, nullable=True)   # null = действует бессрочно
    assembled_amount  = Column(Float, default=1.0)    # норма закладки блюда

    # Метод списания: ASSEMBLE = по ингредиентам, DIRECT = само блюдо целиком
    writeoff_strategy = Column(String(20), default="ASSEMBLE")

    # Стратегия шкалы размеров: COMMON (одна норма) или SPECIFIC (своя норма per размер)
    size_assembly_strategy = Column(String(32), default="COMMON")

    # Подразделения прямого списания (JSON-массив UUID) — для effectiveDirectWriteoffStoreSpecification
    direct_writeoff_departments = Column(Text, default="[]")  # JSON list of UUIDs
    direct_writeoff_inverse     = Column(Boolean, default=True)

    # Текстовые поля техкарты
    technology_description = Column(Text, nullable=True)
    description            = Column(Text, nullable=True)
    appearance             = Column(Text, nullable=True)
    organoleptic           = Column(Text, nullable=True)
    output_comment         = Column(Text, nullable=True)

    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("restaurant_id", "iiko_uuid", name="uq_chart_restaurant"),
    )

    restaurant  = relationship("Restaurant")
    dish        = relationship("Dish", back_populates="charts")
    ingredients = relationship("ChartIngredient", back_populates="chart", cascade="all, delete-orphan")


class ChartIngredient(Base):
    """
    Строка технологической карты — один ингредиент с нормами.
    Ингредиентом может быть товар (product_catalog) или заготовка (другое блюдо).
    """
    __tablename__ = "chart_ingredients"

    id       = Column(Integer, primary_key=True, index=True)
    chart_id = Column(Integer, ForeignKey("assembly_charts.id", ondelete="CASCADE"), nullable=False, index=True)

    iiko_item_uuid       = Column(String(100), nullable=True)   # id строки из IIKO (нужен для save)
    ingredient_iiko_uuid = Column(String(100), nullable=False, index=True)  # productId
    ingredient_name      = Column(String(500), nullable=True, index=True)   # кешируем для поиска
    sort_weight          = Column(Float, default=0.0)

    # Подразделения для строки (null = применяется везде)
    store_departments = Column(Text, nullable=True)   # JSON list of UUIDs или null
    store_inverse     = Column(Boolean, nullable=True)

    # Количества (в основных единицах измерения ингредиента)
    amount_in     = Column(Float, nullable=False)   # брутто — используется в расчётах
    amount_middle = Column(Float, nullable=True)    # нетто
    amount_out    = Column(Float, nullable=True)    # выход

    # Акты проработки (опциональные, обычно 0)
    amount_in1  = Column(Float, default=0.0)
    amount_out1 = Column(Float, default=0.0)
    amount_in2  = Column(Float, default=0.0)
    amount_out2 = Column(Float, default=0.0)
    amount_in3  = Column(Float, default=0.0)
    amount_out3 = Column(Float, default=0.0)

    # Фасовка
    package_count   = Column(Float, default=0.0)
    package_type_id = Column(String(100), nullable=True)  # UUID фасовки из IIKO

    # UUID шкалы размеров (productSizeSpecification) — заполняется только при SPECIFIC стратегии
    product_size_spec_id = Column(String(36), nullable=True)

    # Мягкий FK к product_catalog (NULL если ингредиент — заготовка или удалённый товар)
    product_catalog_id = Column(Integer, ForeignKey("product_catalog.id", ondelete="SET NULL"), nullable=True, index=True)

    chart   = relationship("AssemblyChart", back_populates="ingredients")
    product = relationship("ProductCatalog")
