"""Add product_num and product_name to report_items

Revision ID: 0015
Revises: 0014
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("report_items", sa.Column("product_num", sa.String(100), nullable=True))
    op.add_column("report_items", sa.Column("product_name", sa.String(500), nullable=True))


def downgrade():
    op.drop_column("report_items", "product_name")
    op.drop_column("report_items", "product_num")
