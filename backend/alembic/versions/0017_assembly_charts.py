"""Add assembly charts tables: dishes, assembly_charts, chart_ingredients

Revision ID: 0017
Revises: 0016
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    # Блюда, модификаторы, заготовки из IIKO (номенклатура с техкартами)
    op.create_table(
        "dishes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("iiko_uuid", sa.String(100), nullable=False),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("restaurant_id", "iiko_uuid", name="uq_dish_restaurant"),
    )
    op.create_index("ix_dishes_restaurant_id", "dishes", ["restaurant_id"])
    op.create_index("ix_dishes_iiko_uuid", "dishes", ["iiko_uuid"])

    # Технологические карты (рецепты)
    op.create_table(
        "assembly_charts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.Integer(), sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("iiko_uuid", sa.String(100), nullable=False),
        sa.Column("dish_id", sa.Integer(), sa.ForeignKey("dishes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("assembled_amount", sa.Float(), default=1.0),
        sa.Column("writeoff_strategy", sa.String(20), default="ASSEMBLE"),
        sa.Column("direct_writeoff_departments", sa.Text(), default="[]"),
        sa.Column("direct_writeoff_inverse", sa.Boolean(), default=True),
        sa.Column("technology_description", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("organoleptic", sa.Text(), nullable=True),
        sa.Column("output_comment", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("restaurant_id", "iiko_uuid", name="uq_chart_restaurant"),
    )
    op.create_index("ix_assembly_charts_restaurant_id", "assembly_charts", ["restaurant_id"])
    op.create_index("ix_assembly_charts_iiko_uuid", "assembly_charts", ["iiko_uuid"])
    op.create_index("ix_assembly_charts_dish_id", "assembly_charts", ["dish_id"])

    # Состав техкарты (ингредиенты)
    op.create_table(
        "chart_ingredients",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("chart_id", sa.Integer(), sa.ForeignKey("assembly_charts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("iiko_item_uuid", sa.String(100), nullable=True),
        sa.Column("ingredient_iiko_uuid", sa.String(100), nullable=False),
        sa.Column("ingredient_name", sa.String(500), nullable=True),
        sa.Column("sort_weight", sa.Float(), default=0.0),
        sa.Column("store_departments", sa.Text(), nullable=True),
        sa.Column("store_inverse", sa.Boolean(), nullable=True),
        sa.Column("amount_in", sa.Float(), nullable=False),
        sa.Column("amount_middle", sa.Float(), nullable=True),
        sa.Column("amount_out", sa.Float(), nullable=True),
        sa.Column("amount_in1", sa.Float(), default=0.0),
        sa.Column("amount_out1", sa.Float(), default=0.0),
        sa.Column("amount_in2", sa.Float(), default=0.0),
        sa.Column("amount_out2", sa.Float(), default=0.0),
        sa.Column("amount_in3", sa.Float(), default=0.0),
        sa.Column("amount_out3", sa.Float(), default=0.0),
        sa.Column("package_count", sa.Float(), default=0.0),
        sa.Column("package_type_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_chart_ingredients_chart_id", "chart_ingredients", ["chart_id"])
    op.create_index("ix_chart_ingredients_ingredient_iiko_uuid", "chart_ingredients", ["ingredient_iiko_uuid"])
    op.create_index("ix_chart_ingredients_ingredient_name", "chart_ingredients", ["ingredient_name"])


def downgrade():
    op.drop_table("chart_ingredients")
    op.drop_table("assembly_charts")
    op.drop_table("dishes")
