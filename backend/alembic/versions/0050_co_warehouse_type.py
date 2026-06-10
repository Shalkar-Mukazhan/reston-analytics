"""co: add warehouse_types table and warehouse_type_id to restaurant_warehouses

Revision ID: 0050_co_warehouse_type
Revises: 0049_co_warehouse_writeoff_flag
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_co_warehouse_type"
down_revision = "0049"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.create_table(
        "warehouse_types",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("account_id", sa.Integer(),
                  sa.ForeignKey(f"{_S}.co_accounts.id", ondelete="SET NULL"),
                  nullable=True),
        schema=_S,
    )
    op.add_column(
        "restaurant_warehouses",
        sa.Column("warehouse_type_id", sa.Integer(),
                  sa.ForeignKey(f"{_S}.warehouse_types.id", ondelete="SET NULL"),
                  nullable=True),
        schema=_S,
    )


def downgrade():
    op.drop_column("restaurant_warehouses", "warehouse_type_id", schema=_S)
    op.drop_table("warehouse_types", schema=_S)
