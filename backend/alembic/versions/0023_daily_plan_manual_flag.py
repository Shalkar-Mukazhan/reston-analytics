"""Add is_manual flag to sales_daily_plans

Revision ID: 0023
Revises: 0022
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "sales_daily_plans",
        sa.Column("is_manual", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_column("sales_daily_plans", "is_manual")
