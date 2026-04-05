"""Update reports table and add report_items

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Обновляем reports — убираем лишнее, добавляем нужное
    op.drop_column("reports", "file_path")   # теперь файл генерируется из БД по запросу

    # 2. Создаём report_items — строки отчёта
    op.create_table(
        "report_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, sa.ForeignKey("reports.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("product_catalog.id"), nullable=True),

        # Данные из IIKO
        sa.Column("sales_qty", sa.Float, default=0.0),        # реализация (кол-во)
        sa.Column("writeoff_qty", sa.Float, default=0.0),     # уже списано
        sa.Column("inventory_qty", sa.Float, default=0.0),    # инвентаризация (может быть минус)

        # Расчётные поля
        sa.Column("allowed_qty", sa.Float, default=0.0),      # допустимо по норме
        sa.Column("to_writeoff_qty", sa.Float, default=0.0),  # к списанию
        sa.Column("written_off_pct", sa.Float, default=0.0),  # % уже списанного от реализации

        # Статус строки
        sa.Column("is_over_limit", sa.Boolean, default=False),  # сверх нормы
        sa.Column("status", sa.String(20), default="ok"),
        # ok | over_limit | no_category | no_rate | no_writeoff_needed | needs_check
        sa.Column("comment", sa.String(500)),
    )

    op.create_index("ix_report_items_report_id", "report_items", ["report_id"])
    op.create_index("ix_report_items_status", "report_items", ["status"])


def downgrade():
    op.drop_index("ix_report_items_status", "report_items")
    op.drop_index("ix_report_items_report_id", "report_items")
    op.drop_table("report_items")
    op.add_column("reports", sa.Column("file_path", sa.String(500)))
