"""Add sum columns to report_items

Revision ID: 0011
Revises: 0010
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("report_items", sa.Column("sales_sum", sa.Float(), nullable=True))
    op.add_column("report_items", sa.Column("writeoff_sum", sa.Float(), nullable=True))
    op.add_column("report_items", sa.Column("inventory_sum", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("report_items", "sales_sum")
    op.drop_column("report_items", "writeoff_sum")
    op.drop_column("report_items", "inventory_sum")
