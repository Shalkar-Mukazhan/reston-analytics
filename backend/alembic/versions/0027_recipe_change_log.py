"""Add recipe_change_logs table for rollback support

Revision ID: 0027
Revises: 0026
Create Date: 2026-04-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recipe_change_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False, index=True),
        sa.Column("operation_type", sa.String(50), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("performed_by", sa.String(100), nullable=True),
        sa.Column("effective_date", sa.Date, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("snapshot", sa.Text, nullable=False),
        sa.Column("is_rolled_back", sa.Boolean, nullable=False, server_default="false"),
    )


def downgrade():
    op.drop_table("recipe_change_logs")
