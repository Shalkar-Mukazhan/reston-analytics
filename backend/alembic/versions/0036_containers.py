"""add containers to product_catalog, container_id to ocr_invoice_items

Revision ID: 0036
Revises: 0035
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('product_catalog', sa.Column('containers', JSONB, nullable=True))
    op.add_column('ocr_invoice_items', sa.Column('container_id', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('product_catalog', 'containers')
    op.drop_column('ocr_invoice_items', 'container_id')
