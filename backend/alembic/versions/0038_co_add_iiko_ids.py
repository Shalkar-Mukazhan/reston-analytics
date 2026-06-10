"""coffee_original: add iiko_id to suppliers, unique on products.iiko_article_id

Revision ID: 0038
Revises: 0037
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

SCHEMA = 'coffee_original'


def upgrade():
    op.add_column('suppliers',
        sa.Column('iiko_id', sa.String(100), nullable=True),
        schema=SCHEMA,
    )
    op.create_unique_constraint('uq_co_suppliers_iiko_id', 'suppliers',
        ['iiko_id'], schema=SCHEMA,
    )
    op.create_unique_constraint('uq_co_products_iiko_article_id', 'products',
        ['iiko_article_id'], schema=SCHEMA,
    )


def downgrade():
    op.drop_constraint('uq_co_products_iiko_article_id', 'products', schema=SCHEMA)
    op.drop_constraint('uq_co_suppliers_iiko_id', 'suppliers', schema=SCHEMA)
    op.drop_column('suppliers', 'iiko_id', schema=SCHEMA)
