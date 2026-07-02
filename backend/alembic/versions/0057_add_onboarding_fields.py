"""add onboarding fields

Revision ID: 0057_add_onboarding_fields
Revises: 0056_add_subscriptions
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

revision = "0057_add_onboarding_fields"
down_revision = "0056_add_subscriptions"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    # Добавить поля онбординга в tenants
    op.add_column("tenants",
        sa.Column("company_name", sa.String(255), nullable=True),
        schema=_S)
    op.add_column("tenants",
        sa.Column("phone", sa.String(50), nullable=True),
        schema=_S)
    op.add_column("tenants",
        sa.Column("onboarding_complete", sa.Boolean,
                  nullable=False, server_default="false"),
        schema=_S)

    # Таблица iiko_connections (серверы клиента)
    op.create_table(
        "iiko_connections",
        sa.Column("id", sa.Integer, primary_key=True,
                  autoincrement=True),
        sa.Column("tenant_id", sa.Integer,
                  sa.ForeignKey("coffee_original.tenants.id"),
                  nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(255), nullable=False),
        sa.Column("login", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean,
                  nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S
    )
    op.create_index("ix_iiko_connections_tenant_id",
                    "iiko_connections", ["tenant_id"], schema=_S)


def downgrade():
    op.drop_table("iiko_connections", schema=_S)
    op.drop_column("tenants", "onboarding_complete", schema=_S)
    op.drop_column("tenants", "phone", schema=_S)
    op.drop_column("tenants", "company_name", schema=_S)
