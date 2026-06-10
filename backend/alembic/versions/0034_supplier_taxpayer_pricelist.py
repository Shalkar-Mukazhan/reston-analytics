"""supplier taxpayer_id, iiko_code; supplier_product_mappings; ocr_invoice bin_iin

Revision ID: 0034
Revises: 0033
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade():
    # Расширяем таблицу suppliers
    op.add_column("suppliers", sa.Column("iiko_code",   sa.String(50),  nullable=True))
    op.add_column("suppliers", sa.Column("taxpayer_id", sa.String(50),  nullable=True))
    op.create_index("ix_suppliers_taxpayer_id", "suppliers", ["taxpayer_id"])

    # Маппинг прайс-листа поставщика
    op.create_table(
        "supplier_product_mappings",
        sa.Column("id",                    sa.Integer(), primary_key=True),
        sa.Column("supplier_id",           sa.Integer(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_product_code", sa.String(100), nullable=True),
        sa.Column("supplier_product_name", sa.String(300), nullable=True),
        sa.Column("iiko_product_id",       sa.String(100), nullable=False),
        sa.Column("iiko_product_name",     sa.String(300), nullable=True),
        sa.UniqueConstraint("supplier_id", "supplier_product_code", name="uq_supplier_product_code"),
    )
    op.create_index("ix_spm_supplier_id",   "supplier_product_mappings", ["supplier_id"])
    op.create_index("ix_spm_product_code",  "supplier_product_mappings", ["supplier_product_code"])
    op.create_index("ix_spm_iiko_product",  "supplier_product_mappings", ["iiko_product_id"])

    # БИН/ИИН в OCR-накладных
    op.add_column("ocr_invoices", sa.Column("supplier_bin_iin", sa.String(20), nullable=True))


def downgrade():
    op.drop_column("ocr_invoices", "supplier_bin_iin")
    op.drop_table("supplier_product_mappings")
    op.drop_column("suppliers", "taxpayer_id")
    op.drop_column("suppliers", "iiko_code")
