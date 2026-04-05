"""Fix FK cascade rules and add invoice_number to invoice_items

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. invoice_items: добавляем invoice_number ────────────────
    op.add_column("invoice_items",
        sa.Column("invoice_number", sa.String(100), nullable=True)
    )

    # ── 2. Пересоздаём FK с правильными правилами удаления ────────

    # iiko_sessions.restaurant_id → CASCADE
    op.drop_constraint("iiko_sessions_restaurant_id_fkey", "iiko_sessions", type_="foreignkey")
    op.create_foreign_key(
        "iiko_sessions_restaurant_id_fkey",
        "iiko_sessions", "restaurants", ["restaurant_id"], ["id"],
        ondelete="CASCADE",
    )

    # restaurant_presets.restaurant_id → CASCADE
    op.drop_constraint("restaurant_presets_restaurant_id_fkey", "restaurant_presets", type_="foreignkey")
    op.create_foreign_key(
        "restaurant_presets_restaurant_id_fkey",
        "restaurant_presets", "restaurants", ["restaurant_id"], ["id"],
        ondelete="CASCADE",
    )

    # restaurant_presets.preset_id → CASCADE
    op.drop_constraint("restaurant_presets_preset_id_fkey", "restaurant_presets", type_="foreignkey")
    op.create_foreign_key(
        "restaurant_presets_preset_id_fkey",
        "restaurant_presets", "preset_definitions", ["preset_id"], ["id"],
        ondelete="CASCADE",
    )

    # waste_rates.restaurant_id → CASCADE
    op.drop_constraint("waste_rates_restaurant_id_fkey", "waste_rates", type_="foreignkey")
    op.create_foreign_key(
        "waste_rates_restaurant_id_fkey",
        "waste_rates", "restaurants", ["restaurant_id"], ["id"],
        ondelete="CASCADE",
    )

    # waste_rates.group_id → CASCADE (имя: fk_rates_group)
    op.drop_constraint("fk_rates_group", "waste_rates", type_="foreignkey")
    op.create_foreign_key(
        "fk_rates_group",
        "waste_rates", "product_groups", ["group_id"], ["id"],
        ondelete="CASCADE",
    )

    # report_items.product_id → SET NULL
    op.drop_constraint("report_items_product_id_fkey", "report_items", type_="foreignkey")
    op.create_foreign_key(
        "report_items_product_id_fkey",
        "report_items", "product_catalog", ["product_id"], ["id"],
        ondelete="SET NULL",
    )

    # audit_log.user_id → SET NULL
    op.drop_constraint("audit_log_user_id_fkey", "audit_log", type_="foreignkey")
    op.create_foreign_key(
        "audit_log_user_id_fkey",
        "audit_log", "users", ["user_id"], ["id"],
        ondelete="SET NULL",
    )

    # audit_log.restaurant_id — FK вообще не было, добавляем с SET NULL
    op.create_foreign_key(
        "audit_log_restaurant_id_fkey",
        "audit_log", "restaurants", ["restaurant_id"], ["id"],
        ondelete="SET NULL",
    )

    # reports.restaurant_id → RESTRICT
    op.drop_constraint("reports_restaurant_id_fkey", "reports", type_="foreignkey")
    op.create_foreign_key(
        "reports_restaurant_id_fkey",
        "reports", "restaurants", ["restaurant_id"], ["id"],
        ondelete="RESTRICT",
    )

    # reports.user_id → SET NULL
    op.drop_constraint("reports_user_id_fkey", "reports", type_="foreignkey")
    op.create_foreign_key(
        "reports_user_id_fkey",
        "reports", "users", ["user_id"], ["id"],
        ondelete="SET NULL",
    )

    # invoices.restaurant_id → RESTRICT
    op.drop_constraint("invoices_restaurant_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_restaurant_id_fkey",
        "invoices", "restaurants", ["restaurant_id"], ["id"],
        ondelete="RESTRICT",
    )

    # invoices.user_id → SET NULL
    op.drop_constraint("invoices_user_id_fkey", "invoices", type_="foreignkey")
    op.create_foreign_key(
        "invoices_user_id_fkey",
        "invoices", "users", ["user_id"], ["id"],
        ondelete="SET NULL",
    )

    # waste_metrics.restaurant_id → CASCADE
    op.drop_constraint("waste_metrics_restaurant_id_fkey", "waste_metrics", type_="foreignkey")
    op.create_foreign_key(
        "waste_metrics_restaurant_id_fkey",
        "waste_metrics", "restaurants", ["restaurant_id"], ["id"],
        ondelete="CASCADE",
    )


def downgrade():
    op.drop_column("invoice_items", "invoice_number")
