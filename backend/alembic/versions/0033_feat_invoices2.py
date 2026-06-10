"""restaurant: add feat_invoices2 flag

Revision ID: 0033
Revises: 0032
Create Date: 2026-04-23
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("restaurants", sa.Column("feat_invoices2", sa.Boolean(), nullable=False, server_default="true"))


def downgrade():
    op.drop_column("restaurants", "feat_invoices2")
