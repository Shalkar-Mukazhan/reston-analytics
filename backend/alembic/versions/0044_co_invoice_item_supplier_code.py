"""co: add supplier_product_code to invoice_items

Revision ID: 0044_co_invoice_item_supplier_code
Revises: 0043_co_invoice_document_number
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043_co_invoice_document_number"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoice_items",
        sa.Column("supplier_product_code", sa.String(100), nullable=True),
        schema="coffee_original",
    )


def downgrade():
    op.drop_column("invoice_items", "supplier_product_code", schema="coffee_original")
