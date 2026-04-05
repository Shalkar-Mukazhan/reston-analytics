"""Add checklist day control fields to restaurants

Revision ID: 0026
Revises: 0025
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "restaurants",
        sa.Column("checklist_start_hour", sa.Integer(), nullable=False, server_default="7"),
    )
    op.add_column(
        "restaurants",
        sa.Column("last_checklist_reset_date", sa.Date(), nullable=True),
    )


def downgrade():
    op.drop_column("restaurants", "last_checklist_reset_date")
    op.drop_column("restaurants", "checklist_start_hour")
