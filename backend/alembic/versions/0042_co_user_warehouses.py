"""co: add user_warehouses table

Revision ID: 0042_co_user_warehouses
Revises: 0041
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_warehouses',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('warehouse_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['coffee_original.users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['warehouse_id'], ['coffee_original.restaurant_warehouses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'warehouse_id'),
        schema='coffee_original',
    )


def downgrade():
    op.drop_table('user_warehouses', schema='coffee_original')
