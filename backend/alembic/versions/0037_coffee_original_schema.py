"""create coffee_original schema with core tables

Revision ID: 0037
Revises: 0036
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None

SCHEMA = 'coffee_original'


def upgrade():
    op.execute(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}')

    op.create_table(
        'restaurants',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('code', sa.String(20), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('base_url', sa.String(255), nullable=False),
        sa.Column('iiko_login', sa.String(100), nullable=False),
        sa.Column('iiko_password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        schema=SCHEMA,
    )

    op.create_table(
        'restaurant_warehouses',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('restaurant_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.restaurants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('iiko_store_id', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        schema=SCHEMA,
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('email', sa.String(150), nullable=False, unique=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='user'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        schema=SCHEMA,
    )

    op.create_table(
        'user_restaurants',
        sa.Column('user_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.users.id', ondelete='CASCADE'),
                  primary_key=True),
        sa.Column('restaurant_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.restaurants.id', ondelete='CASCADE'),
                  primary_key=True),
        schema=SCHEMA,
    )

    op.create_table(
        'suppliers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(150), nullable=False),
        sa.Column('bin', sa.String(20), nullable=True),
        sa.Column('contact', sa.String(255), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        schema=SCHEMA,
    )

    op.create_table(
        'products',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('iiko_article_id', sa.String(100), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('unit', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        schema=SCHEMA,
    )

    op.create_table(
        'product_mapping',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('supplier_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.suppliers.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('product_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.products.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('supplier_product_name', sa.String(255), nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        'invoices',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('restaurant_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.restaurants.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('warehouse_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.restaurant_warehouses.id', ondelete='RESTRICT'),
                  nullable=False),
        sa.Column('supplier_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.suppliers.id', ondelete='RESTRICT'),
                  nullable=False),
        sa.Column('invoice_date', sa.Date, nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.users.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        schema=SCHEMA,
    )

    op.create_table(
        'invoice_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('invoice_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.invoices.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('product_id', sa.Integer,
                  sa.ForeignKey(f'{SCHEMA}.products.id', ondelete='RESTRICT'),
                  nullable=True),
        sa.Column('supplier_product_name', sa.String(255), nullable=True),
        sa.Column('qty', sa.Numeric(12, 3), nullable=False),
        sa.Column('price', sa.Numeric(12, 2), nullable=False),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table('invoice_items', schema=SCHEMA)
    op.drop_table('invoices', schema=SCHEMA)
    op.drop_table('product_mapping', schema=SCHEMA)
    op.drop_table('products', schema=SCHEMA)
    op.drop_table('suppliers', schema=SCHEMA)
    op.drop_table('user_restaurants', schema=SCHEMA)
    op.drop_table('users', schema=SCHEMA)
    op.drop_table('restaurant_warehouses', schema=SCHEMA)
    op.drop_table('restaurants', schema=SCHEMA)
    op.execute(f'DROP SCHEMA IF EXISTS {SCHEMA}')
