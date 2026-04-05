"""Add google_sheet_url to restaurants

Revision ID: 0025
Revises: 0024
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "restaurants",
        sa.Column("google_sheet_url", sa.String(500), nullable=True),
    )


def downgrade():
    op.drop_column("restaurants", "google_sheet_url")
