"""Add suppliers table, store_id to restaurants, clean invoices

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Таблица поставщиков IIKO
    op.create_table(
        "suppliers",
        sa.Column("id",            sa.Integer, primary_key=True),
        sa.Column("iiko_uuid",     sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name",          sa.String(255), nullable=False),
    )

    # 2. store_id в рестораны (UUID склада IIKO — нужен для отправки накладных)
    op.add_column("restaurants",
        sa.Column("store_id", sa.String(100), nullable=True)
    )

    # 3. invoices: убираем file_path, добавляем supplier_id + total суммы
    op.drop_column("invoices", "file_path")
    op.add_column("invoices",
        sa.Column("supplier_id", sa.Integer,
                  sa.ForeignKey("suppliers.id", ondelete="SET NULL"),
                  nullable=True)
    )
    op.add_column("invoices", sa.Column("total_sum",     sa.Float, nullable=True))
    op.add_column("invoices", sa.Column("total_sum_vat", sa.Float, nullable=True))


def downgrade():
    op.drop_column("invoices", "total_sum_vat")
    op.drop_column("invoices", "total_sum")
    op.drop_column("invoices", "supplier_id")
    op.add_column("invoices", sa.Column("file_path", sa.String(500)))
    op.drop_column("restaurants", "store_id")
    op.drop_table("suppliers")
