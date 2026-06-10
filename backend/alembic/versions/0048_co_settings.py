"""co: global settings table (inventory preset UUID etc.)

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.create_table(
        "co_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        schema=_S,
    )


def downgrade():
    op.drop_table("co_settings", schema=_S)
