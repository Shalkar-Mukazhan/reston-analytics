"""Add abl_products and invoice_items tables

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Маппинг ABL артикулов → товары IIKO
    op.create_table(
        "abl_products",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("abl_article",      sa.String(50),  unique=True, nullable=False, index=True),
        sa.Column("abl_main_article", sa.String(50),  nullable=False, index=True),
        sa.Column("name",             sa.String(300), nullable=False),
        sa.Column("supplier",         sa.String(255)),
        sa.Column("price",            sa.Float),
        sa.Column("price_vat",        sa.Float),
        # Связь с IIKO через product_catalog
        sa.Column("product_catalog_id", sa.Integer,
                  sa.ForeignKey("product_catalog.id", ondelete="SET NULL"),
                  nullable=True, index=True),
    )

    # 2. Строки накладной ABL
    op.create_table(
        "invoice_items",
        sa.Column("id",             sa.Integer, primary_key=True),
        sa.Column("invoice_id",     sa.Integer,
                  sa.ForeignKey("invoices.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # Ссылка на маппинг (nullable — если артикул не найден в справочнике)
        sa.Column("abl_product_id", sa.Integer,
                  sa.ForeignKey("abl_products.id", ondelete="SET NULL"),
                  nullable=True),
        # Сырые данные из накладной
        sa.Column("abl_article",  sa.String(50)),   # артикул как есть в файле
        sa.Column("name",         sa.String(300)),  # наименование из накладной
        sa.Column("quantity",     sa.Float),
        sa.Column("unit_type",    sa.String(20)),
        sa.Column("unit_price",   sa.Float),        # цена без НДС
        sa.Column("unit_price_vat", sa.Float),      # цена с НДС
        sa.Column("total_price",  sa.Float),        # сумма без НДС
        sa.Column("total_price_vat", sa.Float),     # сумма с НДС
    )

    op.create_index("ix_invoice_items_abl_product_id", "invoice_items", ["abl_product_id"])


def downgrade():
    op.drop_index("ix_invoice_items_abl_product_id", "invoice_items")
    op.drop_table("invoice_items")
    op.drop_table("abl_products")
