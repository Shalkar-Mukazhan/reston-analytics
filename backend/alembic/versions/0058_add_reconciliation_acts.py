"""add co_reconciliation_acts table

Revision ID: 0058_add_reconciliation_acts
Revises: 0057_add_onboarding_fields
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = "0058_add_reconciliation_acts"
down_revision = "0057_add_onboarding_fields"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.create_table(
        "co_reconciliation_acts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("restaurant_id", sa.Integer,
                  sa.ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("supplier_id", sa.Integer,
                  sa.ForeignKey(f"{_S}.suppliers.id", ondelete="RESTRICT"),
                  nullable=False),
        sa.Column("period_from", sa.Date, nullable=False),
        sa.Column("period_to", sa.Date, nullable=False),
        sa.Column("credit_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("debit_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("iiko_invoices_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("delta", sa.Numeric(14, 2), nullable=False),
        sa.Column("verdict", sa.String(20), nullable=False),
        sa.Column("rows_json", sa.JSON, nullable=True),
        sa.Column("extra_invoices_json", sa.JSON, nullable=True),
        sa.Column("source_filename", sa.String(255), nullable=True),
        sa.Column("created_by", sa.Integer,
                  sa.ForeignKey(f"{_S}.users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        schema=_S,
    )
    op.create_index("ix_co_reconciliation_acts_restaurant_id",
                     "co_reconciliation_acts", ["restaurant_id"], schema=_S)
    op.create_index("ix_co_reconciliation_acts_supplier_id",
                     "co_reconciliation_acts", ["supplier_id"], schema=_S)


def downgrade():
    op.drop_table("co_reconciliation_acts", schema=_S)
