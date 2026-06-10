"""system_settings table

Revision ID: 0030
Revises: 0029
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key",   sa.String(100), primary_key=True),
        sa.Column("value", sa.Text,        nullable=False, server_default=""),
    )
    # Дефолт: О системе скрыта для CO
    op.execute("INSERT INTO system_settings (key, value) VALUES ('show_about_co', 'false')")


def downgrade():
    op.drop_table("system_settings")
