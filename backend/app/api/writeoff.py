from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.restaurant import Restaurant
from app.models.audit import AuditLog
from app.services.iiko import post_writeoff

router = APIRouter(prefix="/api/writeoff", tags=["writeoff"])


class WriteoffRequest(BaseModel):
    restaurant_id: int
    payload: dict  # Тело документа списания в формате IIKO


@router.post("/post")
def post_writeoff_document(
    body: WriteoffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    restaurant = db.query(Restaurant).filter(Restaurant.id == body.restaurant_id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Ресторан не найден")

    if current_user.role != "co":
        allowed_ids = [r.id for r in current_user.restaurants]
        if restaurant.id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Нет доступа к этому ресторану")

    result = post_writeoff(db, restaurant, body.payload)

    db.add(AuditLog(
        user_id=current_user.id,
        restaurant_id=restaurant.id,
        action="post_writeoff",
        details=str(body.payload)[:500],
    ))
    db.commit()

    return result
