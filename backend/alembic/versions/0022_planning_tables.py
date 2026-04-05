"""Add planning tables: monthly targets, daily facts, daily plans

Revision ID: 0022
Revises: 0021
Create Date: 2026-04-04
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sales_monthly_targets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("gc_target", sa.Integer, nullable=True),
        sa.Column("sales_target", sa.Numeric(14, 2), nullable=True),
        sa.Column("set_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "month", name="uq_monthly_target"),
    )

    op.create_table(
        "sales_daily_facts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("gc_fact", sa.Integer, nullable=True),
        sa.Column("sales_fact", sa.Numeric(14, 2), nullable=True),
        sa.Column("av_check_fact", sa.Numeric(10, 2), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "date", name="uq_daily_fact"),
    )

    op.create_table(
        "sales_daily_plans",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("gc_plan", sa.Integer, nullable=True),
        sa.Column("sales_plan", sa.Numeric(14, 2), nullable=True),
        sa.Column("av_check_plan", sa.Numeric(10, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("restaurant_id", "date", name="uq_daily_plan"),
    )


def downgrade():
    op.drop_table("sales_daily_plans")
    op.drop_table("sales_daily_facts")
    op.drop_table("sales_monthly_targets")
