"""co: add total_sum to co_writeoff_acts and resigned_sum to co_writeoff_items

Revision ID: 0052_co_act_total_sum
Revises: 0051_co_act_inventory_datetime
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0052_co_act_total_sum"
down_revision = "0051_co_act_inventory_datetime"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.add_column(
        "co_writeoff_acts",
        sa.Column("total_sum", sa.Numeric(14, 2), nullable=True),
        schema=_S,
    )
    op.add_column(
        "co_writeoff_items",
        sa.Column("resigned_sum", sa.Numeric(14, 2), nullable=True),
        schema=_S,
    )


def downgrade():
    op.drop_column("co_writeoff_acts", "total_sum", schema=_S)
    op.drop_column("co_writeoff_items", "resigned_sum", schema=_S)
