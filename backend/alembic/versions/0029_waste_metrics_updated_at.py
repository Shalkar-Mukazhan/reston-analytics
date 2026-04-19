"""waste_metrics: add updated_at, upsert instead of delete+insert

Revision ID: 0029
Revises: 0028
Create Date: 2026-04-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "waste_metrics",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
        ),
    )
    # Заполняем существующие строки значением created_at
    op.execute("UPDATE waste_metrics SET updated_at = created_at WHERE updated_at IS NULL")


def downgrade():
    op.drop_column("waste_metrics", "updated_at")
