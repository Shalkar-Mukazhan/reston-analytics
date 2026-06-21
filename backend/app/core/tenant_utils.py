"""Shared multi-tenant helpers for coffee_original routers."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.co_models import CoRestaurant, CoUser


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
