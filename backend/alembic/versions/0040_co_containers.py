"""coffee_original: product containers table + container_id in product_mapping

Revision ID: 0040
Revises: 0039
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None

SCHEMA = 'coffee_original'


def upgrade():
    op.create_table(
        'product_containers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('product_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.products.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('iiko_container_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('count', sa.Numeric(10, 3), nullable=False),
        schema=SCHEMA,
    )
    op.add_column('product_mapping',
        sa.Column('container_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.product_containers.id', ondelete='SET NULL'),
                  nullable=True),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_column('product_mapping', 'container_id', schema=SCHEMA)
    op.drop_table('product_containers', schema=SCHEMA)
