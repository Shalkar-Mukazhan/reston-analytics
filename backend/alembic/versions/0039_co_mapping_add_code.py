"""coffee_original: add supplier_product_code to product_mapping

Revision ID: 0039
Revises: 0038
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

SCHEMA = 'coffee_original'


def upgrade():
    op.add_column('product_mapping',
        sa.Column('supplier_product_code', sa.String(100), nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_column('product_mapping', 'supplier_product_code', schema=SCHEMA)
