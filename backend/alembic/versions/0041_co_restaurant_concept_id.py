"""co: add iiko_concept_id to restaurants

Revision ID: 0041_co_restaurant_concept_id
Revises: 0040_co_containers
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'restaurants',
        sa.Column('iiko_concept_id', sa.String(100), nullable=True),
        schema='coffee_original',
    )


def downgrade():
    op.drop_column('restaurants', 'iiko_concept_id', schema='coffee_original')
