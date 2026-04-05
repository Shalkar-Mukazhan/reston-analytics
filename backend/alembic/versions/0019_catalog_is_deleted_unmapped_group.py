"""Add is_deleted to product_catalog, create UNMAPPED group

Revision ID: 0019
Revises: 0018
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Добавляем is_deleted в product_catalog
    op.add_column(
        "product_catalog",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
    )

    # 2. Создаём группу UNMAPPED если её ещё нет
    op.execute("""
        INSERT INTO product_groups (name, account_id)
        SELECT 'UNMAPPED', NULL
        WHERE NOT EXISTS (SELECT 1 FROM product_groups WHERE name = 'UNMAPPED')
    """)


def downgrade():
    op.drop_column("product_catalog", "is_deleted")
    op.execute("DELETE FROM product_groups WHERE name = 'UNMAPPED'")
