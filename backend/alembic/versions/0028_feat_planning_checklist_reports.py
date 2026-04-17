"""Add feat_planning, feat_checklist, feat_reports feature flags to restaurants

Revision ID: 0028
Revises: 0027
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("restaurants", sa.Column("feat_reports",   sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("restaurants", sa.Column("feat_planning",  sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("restaurants", sa.Column("feat_checklist", sa.Boolean(), nullable=False, server_default="true"))


def downgrade():
    op.drop_column("restaurants", "feat_checklist")
    op.drop_column("restaurants", "feat_planning")
    op.drop_column("restaurants", "feat_reports")
