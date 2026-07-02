"""co: add subscriptions, invoice_usage, google_oauth tables (SaaS billing + OAuth)

Revision ID: 0056_add_subscriptions
Revises: 0055_finalize_tenant_id
Create Date: 2026-07-01
"""
from alembic import op
import sqlalchemy as sa

revision = "0056_add_subscriptions"
down_revision = "0055_finalize_tenant_id"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    # Таблица subscriptions
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer,
                  sa.ForeignKey("coffee_original.tenants.id"),
                  nullable=False),
        sa.Column("plan", sa.String(50), nullable=False,
                  server_default="trial"),
        sa.Column("status", sa.String(50), nullable=False,
                  server_default="active"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S,
    )
    op.create_index("ix_subscriptions_tenant_id",
                    "subscriptions", ["tenant_id"], schema=_S)

    # Таблица invoice_usage (счётчик накладных для биллинга)
    op.create_table(
        "invoice_usage",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer,
                  sa.ForeignKey("coffee_original.tenants.id"),
                  nullable=False),
        sa.Column("year_month", sa.String(7), nullable=False),
        sa.Column("count", sa.Integer, nullable=False,
                  server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S,
    )
    op.create_index("ix_invoice_usage_tenant_month",
                    "invoice_usage",
                    ["tenant_id", "year_month"], schema=_S)
    op.create_unique_constraint(
        "uq_invoice_usage_tenant_month",
        "invoice_usage",
        ["tenant_id", "year_month"], schema=_S,
    )

    # Таблица google_oauth (связь Google аккаунта с юзером)
    op.create_table(
        "google_oauth",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("coffee_original.users.id"),
                  nullable=False),
        sa.Column("google_sub", sa.String(255),
                  nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S,
    )
    op.create_index("ix_google_oauth_user_id",
                    "google_oauth", ["user_id"], schema=_S)

    # Seed: подписка для Coffee Original (уже существующий тенант)
    op.execute("""
        INSERT INTO coffee_original.subscriptions
            (tenant_id, plan, status, created_at)
        VALUES (1, 'pro', 'active', NOW())
    """)


def downgrade():
    op.drop_table("google_oauth", schema=_S)
    op.drop_index("ix_invoice_usage_tenant_month",
                  table_name="invoice_usage", schema=_S)
    op.drop_table("invoice_usage", schema=_S)
    op.drop_index("ix_subscriptions_tenant_id",
                  table_name="subscriptions", schema=_S)
    op.drop_table("subscriptions", schema=_S)
