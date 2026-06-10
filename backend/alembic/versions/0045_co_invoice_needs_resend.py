"""co: add needs_resend flag to invoices

Revision ID: 0045
Revises: 0044
Create Date: 2026-05-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoices",
        sa.Column("needs_resend", sa.Boolean(), nullable=False, server_default="false"),
        schema="coffee_original",
    )


def downgrade():
    op.drop_column("invoices", "needs_resend", schema="coffee_original")
