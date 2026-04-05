"""Make product_catalog.group_id nullable (for unmapped products from IIKO sync)

Revision ID: 0014
Revises: 0013
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    # Разрешаем NULL в group_id — товары из IIKO приходят без группы (unmapped)
    op.alter_column(
        "product_catalog", "group_id",
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade():
    # Перед обратным изменением нужно убедиться что NULL нет
    op.execute("DELETE FROM product_catalog WHERE group_id IS NULL")
    op.alter_column(
        "product_catalog", "group_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
