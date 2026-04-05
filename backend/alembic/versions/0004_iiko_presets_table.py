"""Extract presets from restaurants into iiko_presets table

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Создаём таблицу пресетов
    op.create_table(
        "iiko_presets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("preset_type", sa.String(50), nullable=False),   # sales, writeoff, inventory...
        sa.Column("preset_uuid", sa.String(100), nullable=False),
        sa.UniqueConstraint("restaurant_id", "preset_type", name="uq_iiko_preset"),
    )

    # 2. Переносим данные из JSON колонки
    op.execute("""
        INSERT INTO iiko_presets (restaurant_id, preset_type, preset_uuid)
        SELECT
            id,
            key,
            value
        FROM restaurants,
             json_each_text(presets::json)
        WHERE presets IS NOT NULL
    """)

    # 3. Удаляем JSON колонку из restaurants
    op.drop_column("restaurants", "presets")


def downgrade():
    op.add_column("restaurants", sa.Column("presets", sa.JSON))
    op.execute("""
        UPDATE restaurants r
        SET presets = (
            SELECT json_object_agg(preset_type, preset_uuid)
            FROM iiko_presets ip
            WHERE ip.restaurant_id = r.id
        )
    """)
    op.drop_table("iiko_presets")
