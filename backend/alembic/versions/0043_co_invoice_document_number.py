"""co: add document_number to invoices

Revision ID: 0043_co_invoice_document_number
Revises: 0042_co_user_warehouses
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0043_co_invoice_document_number"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column("document_number", sa.String(100), nullable=True),
        schema="coffee_original",
    )


def downgrade():
    op.drop_column("invoices", "document_number", schema="coffee_original")
