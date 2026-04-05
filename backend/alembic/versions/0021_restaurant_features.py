"""Add feature flags to restaurants

Revision ID: 0021
Revises: 0020
Create Date: 2026-04-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("restaurants", sa.Column("feat_invoices", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("restaurants", sa.Column("feat_analytics", sa.Boolean(), nullable=False, server_default="true"))


def downgrade():
    op.drop_column("restaurants", "feat_analytics")
    op.drop_column("restaurants", "feat_invoices")
