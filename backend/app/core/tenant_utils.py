"""Shared multi-tenant helpers for coffee_original routers."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.co_models import (
    CoRestaurant,
    CoWarehouse,
    CoSupplier,
    CoProduct,
    CoProductMapping,
    CoProductContainer,
    CoUser,
)


def load_restaurant(db: Session, restaurant_id: int, user: CoUser) -> CoRestaurant:
    """Загружает ресторан с проверкой tenant_id. 404 если не найден."""
    restaurant = db.query(CoRestaurant).filter(
        CoRestaurant.id == restaurant_id,
        CoRestaurant.tenant_id == user.tenant_id,
    ).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ресторан не найден или нет доступа",
        )
    return restaurant


def load_warehouse(db: Session, warehouse_id: int, user: CoUser) -> CoWarehouse:
    """Загружает склад с проверкой что ресторан принадлежит тенанту."""
    wh = db.query(CoWarehouse).filter(
        CoWarehouse.id == warehouse_id,
    ).first()
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Склад не найден",
        )
    load_restaurant(db, wh.restaurant_id, user)  # tenant-гейт
    return wh


def load_supplier(db: Session, supplier_id: int, user: CoUser) -> CoSupplier:
    """Загружает поставщика с проверкой tenant_id. 404 если чужой/нет."""
    supplier = db.query(CoSupplier).filter(
        CoSupplier.id == supplier_id,
        CoSupplier.tenant_id == user.tenant_id,
    ).first()
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Поставщик не найден",
        )
    return supplier


def load_product(db: Session, product_id: int, user: CoUser) -> CoProduct:
    """Загружает товар с проверкой tenant_id. 404 если чужой/нет."""
    product = db.query(CoProduct).filter(
        CoProduct.id == product_id,
        CoProduct.tenant_id == user.tenant_id,
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Товар не найден",
        )
    return product


def load_mapping(db: Session, mapping_id: int, user: CoUser) -> CoProductMapping:
    """Загружает маппинг через поставщика с tenant-гейтом. 404 если чужой/нет."""
    mapping = db.query(CoProductMapping).join(
        CoSupplier, CoProductMapping.supplier_id == CoSupplier.id
    ).filter(
        CoProductMapping.id == mapping_id,
        CoSupplier.tenant_id == user.tenant_id,
    ).first()
    if not mapping:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Маппинг не найден",
        )
    return mapping


def load_container(db: Session, container_id: int, user: CoUser) -> CoProductContainer:
    """Загружает контейнер через товар с tenant-гейтом. 404 если чужой/нет."""
    container = db.query(CoProductContainer).join(
        CoProduct, CoProductContainer.product_id == CoProduct.id
    ).filter(
        CoProductContainer.id == container_id,
        CoProduct.tenant_id == user.tenant_id,
    ).first()
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Контейнер не найден",
        )
    return container
