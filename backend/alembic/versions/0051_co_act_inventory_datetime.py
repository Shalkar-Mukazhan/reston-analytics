"""co: add inventory_datetime and writeoff_datetime to co_writeoff_acts

Revision ID: 0051_co_act_inventory_datetime
Revises: 0050_co_warehouse_type
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_co_act_inventory_datetime"
down_revision = "0050_co_warehouse_type"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.add_column(
        "co_writeoff_acts",
        sa.Column("inventory_datetime", sa.DateTime(timezone=True), nullable=True),
        schema=_S,
    )
    op.add_column(
        "co_writeoff_acts",
        sa.Column("writeoff_datetime", sa.DateTime(timezone=True), nullable=True),
        schema=_S,
    )


def downgrade():
    op.drop_column("co_writeoff_acts", "writeoff_datetime", schema=_S)
    op.drop_column("co_writeoff_acts", "inventory_datetime", schema=_S)
