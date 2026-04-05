"""Initial tables

Revision ID: 0001
Revises:
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="store"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "restaurants",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("department_name", sa.String(100)),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("iiko_login", sa.String(100), nullable=False),
        sa.Column("iiko_password_hash", sa.String(255), nullable=False),
        sa.Column("presets", sa.JSON),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )

    op.create_table(
        "user_restaurants",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), primary_key=True),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_type", sa.String(10), server_default="month"),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("file_path", sa.String(500)),
        sa.Column("error_message", sa.String(1000)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "waste_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("waste_pct", sa.Float),
        sa.Column("shortage_sum", sa.Float),
        sa.Column("revenue_sum", sa.Float),
        sa.Column("complete_waste_sum", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "iiko_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey("restaurants.id"), nullable=False),
        sa.Column("session_key", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("restaurant_id", sa.Integer, nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("details", sa.Text),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("audit_log")
    op.drop_table("iiko_sessions")
    op.drop_table("waste_metrics")
    op.drop_table("reports")
    op.drop_table("user_restaurants")
    op.drop_table("restaurants")
    op.drop_table("users")
