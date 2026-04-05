"""Extend waste_metrics with new KPI columns

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("waste_metrics", sa.Column("report_id", sa.Integer(), sa.ForeignKey("reports.id", ondelete="SET NULL"), nullable=True))
    op.add_column("waste_metrics", sa.Column("shortage_pct", sa.Float(), nullable=True, server_default="0"))
    op.add_column("waste_metrics", sa.Column("writeoff_pct", sa.Float(), nullable=True, server_default="0"))
    op.add_column("waste_metrics", sa.Column("to_writeoff_qty", sa.Float(), nullable=True, server_default="0"))
    op.add_column("waste_metrics", sa.Column("over_limit_count", sa.Integer(), nullable=True, server_default="0"))


def downgrade():
    op.drop_column("waste_metrics", "report_id")
    op.drop_column("waste_metrics", "shortage_pct")
    op.drop_column("waste_metrics", "writeoff_pct")
    op.drop_column("waste_metrics", "to_writeoff_qty")
    op.drop_column("waste_metrics", "over_limit_count")
