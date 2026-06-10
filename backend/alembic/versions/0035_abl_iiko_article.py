"""add iiko_article to abl_products

Revision ID: 0035_abl_iiko_article
Revises: 0034_supplier_taxpayer_pricelist
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('abl_products', sa.Column('iiko_article', sa.String(100), nullable=True))
    op.create_index('ix_abl_products_iiko_article', 'abl_products', ['iiko_article'])


def downgrade():
    op.drop_index('ix_abl_products_iiko_article', 'abl_products')
    op.drop_column('abl_products', 'iiko_article')
