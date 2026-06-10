"""co: add is_writeoff_default flag to restaurant_warehouses

Revision ID: 0049
Revises: 0048
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "restaurant_warehouses",
        sa.Column("is_writeoff_default", sa.Boolean, nullable=False, server_default="false"),
        schema="coffee_original",
    )


def downgrade():
    op.drop_column("restaurant_warehouses", "is_writeoff_default", schema="coffee_original")
