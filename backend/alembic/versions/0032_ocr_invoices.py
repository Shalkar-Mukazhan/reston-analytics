"""ocr_invoices and ocr_invoice_items tables

Revision ID: 0032
Revises: 0031
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ocr_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("supplier_name_raw", sa.String(255), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("invoice_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="processed"),
        sa.Column("total_sum", sa.Float(), nullable=True),
        sa.Column("total_sum_vat", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ocr_invoices_id", "ocr_invoices", ["id"])

    op.create_table(
        "ocr_invoice_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("invoice_id", sa.Integer(), sa.ForeignKey("ocr_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_code", sa.String(100), nullable=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("unit_type", sa.String(20), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("unit_price", sa.Float(), nullable=True),
        sa.Column("unit_price_vat", sa.Float(), nullable=True),
        sa.Column("total_price", sa.Float(), nullable=True),
        sa.Column("total_price_vat", sa.Float(), nullable=True),
        sa.Column("vat_amount", sa.Float(), nullable=True),
        sa.Column("iiko_product_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_ocr_invoice_items_id", "ocr_invoice_items", ["id"])
    op.create_index("ix_ocr_invoice_items_invoice_id", "ocr_invoice_items", ["invoice_id"])


def downgrade():
    op.drop_table("ocr_invoice_items")
    op.drop_table("ocr_invoices")
