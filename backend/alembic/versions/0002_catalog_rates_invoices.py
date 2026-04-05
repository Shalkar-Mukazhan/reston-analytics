"""Add product_catalog, waste_rates, invoices

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Справочник товаров
    op.create_table(
        "product_catalog",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("product_iiko_id", sa.String(100), unique=True, nullable=False),
        sa.Column("product_num", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("unit_type", sa.String(20)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_product_catalog_product_num", "product_catalog", ["product_num"])
    op.create_index("ix_product_catalog_product_iiko_id", "product_catalog", ["product_iiko_id"])

    # Нормы списания
    op.create_table(
        "waste_rates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("group_name", sa.String(255), nullable=False),
        sa.Column("rate_pct", sa.Float, nullable=False),
        sa.UniqueConstraint("restaurant_id", "group_name", name="uq_waste_rate"),
    )

    # Накладные ABL
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("invoice_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), server_default="uploaded"),
        sa.Column("file_path", sa.String(500)),
        sa.Column("error_message", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Уникальность метрик — нельзя дублировать один период
    op.create_unique_constraint(
        "uq_waste_metrics_restaurant_period",
        "waste_metrics",
        ["restaurant_id", "period"],
    )

    # Добавляем date_from, date_to в reports
    op.add_column("reports", sa.Column("date_from", sa.Date))
    op.add_column("reports", sa.Column("date_to", sa.Date))


def downgrade():
    op.drop_column("reports", "date_to")
    op.drop_column("reports", "date_from")
    op.drop_constraint("uq_waste_metrics_restaurant_period", "waste_metrics")
    op.drop_table("invoices")
    op.drop_table("waste_rates")
    op.drop_table("product_catalog")
