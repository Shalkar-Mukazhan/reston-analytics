"""Refactor presets to many-to-many

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Таблица уникальных пресетов (UUID хранится один раз)
    op.create_table(
        "preset_definitions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("preset_type", sa.String(50), nullable=False),
        sa.Column("preset_uuid", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.UniqueConstraint("preset_type", "preset_uuid", name="uq_preset_definition"),
    )

    # 2. Таблица связи ресторан ↔ пресет
    op.create_table(
        "restaurant_presets",
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), primary_key=True),
        sa.Column("preset_id", sa.Integer, sa.ForeignKey("preset_definitions.id"), primary_key=True),
    )

    # 3. Переносим данные: сначала уникальные пресеты
    op.execute("""
        INSERT INTO preset_definitions (preset_type, preset_uuid)
        SELECT DISTINCT preset_type, preset_uuid
        FROM iiko_presets
        ORDER BY preset_type
    """)

    # 4. Создаём связи ресторан ↔ пресет
    op.execute("""
        INSERT INTO restaurant_presets (restaurant_id, preset_id)
        SELECT ip.restaurant_id, pd.id
        FROM iiko_presets ip
        JOIN preset_definitions pd
          ON ip.preset_type = pd.preset_type
         AND ip.preset_uuid  = pd.preset_uuid
    """)

    # 5. Удаляем старую таблицу
    op.drop_table("iiko_presets")


def downgrade():
    op.create_table(
        "iiko_presets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("preset_type", sa.String(50), nullable=False),
        sa.Column("preset_uuid", sa.String(100), nullable=False),
        sa.UniqueConstraint("restaurant_id", "preset_type", name="uq_iiko_preset"),
    )
    op.execute("""
        INSERT INTO iiko_presets (restaurant_id, preset_type, preset_uuid)
        SELECT rp.restaurant_id, pd.preset_type, pd.preset_uuid
        FROM restaurant_presets rp
        JOIN preset_definitions pd ON rp.preset_id = pd.id
    """)
    op.drop_table("restaurant_presets")
    op.drop_table("preset_definitions")
