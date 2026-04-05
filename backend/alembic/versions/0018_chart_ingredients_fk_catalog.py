"""Link chart_ingredients to product_catalog via soft FK

Revision ID: 0018
Revises: 0017
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "chart_ingredients",
        sa.Column(
            "product_catalog_id",
            sa.Integer(),
            sa.ForeignKey("product_catalog.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_chart_ingredients_product_catalog_id", "chart_ingredients", ["product_catalog_id"])

    # Заполняем сразу — матчим по ingredient_iiko_uuid = product_iiko_id
    op.execute("""
        UPDATE chart_ingredients ci
        SET product_catalog_id = pc.id
        FROM product_catalog pc
        WHERE ci.ingredient_iiko_uuid = pc.product_iiko_id
    """)


def downgrade():
    op.drop_index("ix_chart_ingredients_product_catalog_id", "chart_ingredients")
    op.drop_column("chart_ingredients", "product_catalog_id")
