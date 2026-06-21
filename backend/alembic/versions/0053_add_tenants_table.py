"""co: add tenants table (multi-tenancy step 1) + seed Coffee Original

Revision ID: 0053_add_tenants_table
Revises: 0052_co_act_total_sum
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0053_add_tenants_table"
down_revision = "0052_co_act_total_sum"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="chain"),
        sa.Column("plan", sa.String(50), nullable=False, server_default="pro"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S,
    )

    op.execute("""
        INSERT INTO coffee_original.tenants
            (slug, name, type, plan, is_active, created_at)
        VALUES
            ('coffee-original', 'Coffee Original', 'chain', 'pro', true, NOW())
    """)


def downgrade():
    op.drop_table("tenants", schema=_S)
