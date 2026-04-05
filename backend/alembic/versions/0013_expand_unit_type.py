"""Expand unit_type and preset_type columns

Revision ID: 0013
Revises: 0012
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    # unit_type VARCHAR(20) → VARCHAR(100): IIKO возвращает UUID (36 chars) или длинные названия
    op.alter_column(
        "product_catalog", "unit_type",
        existing_type=sa.String(20),
        type_=sa.String(100),
        existing_nullable=True,
    )
    # preset_type VARCHAR(50) → VARCHAR(100): разрешаем произвольные типы отчётов
    op.alter_column(
        "preset_definitions", "preset_type",
        existing_type=sa.String(50),
        type_=sa.String(100),
        existing_nullable=False,
    )


def downgrade():
    op.alter_column(
        "product_catalog", "unit_type",
        existing_type=sa.String(100),
        type_=sa.String(20),
        existing_nullable=True,
    )
    op.alter_column(
        "preset_definitions", "preset_type",
        existing_type=sa.String(100),
        type_=sa.String(50),
        existing_nullable=False,
    )
