"""Add size_assembly_strategy to assembly_charts and product_size_spec_id to chart_ingredients

Revision ID: 0020
Revises: 0019
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    # Стратегия шкалы размеров на уровне техкарты (COMMON или SPECIFIC)
    op.add_column(
        "assembly_charts",
        sa.Column("size_assembly_strategy", sa.String(32), nullable=False, server_default="COMMON"),
    )
    # UUID шкалы размеров на уровне ингредиента (заполняется только при SPECIFIC)
    op.add_column(
        "chart_ingredients",
        sa.Column("product_size_spec_id", sa.String(36), nullable=True),
    )


def downgrade():
    op.drop_column("chart_ingredients", "product_size_spec_id")
    op.drop_column("assembly_charts", "size_assembly_strategy")
