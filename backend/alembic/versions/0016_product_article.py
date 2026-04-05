"""Add product_article to product_catalog (IIKO OLAP Product.Num key)

Revision ID: 0016
Revises: 0015
Create Date: 2026-04-02
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    # product_article = IIKO num (артикул) типа "12804-001" — именно это OLAP возвращает в Product.Num
    op.add_column("product_catalog", sa.Column("product_article", sa.String(100), nullable=True, index=True))


def downgrade():
    op.drop_column("product_catalog", "product_article")
