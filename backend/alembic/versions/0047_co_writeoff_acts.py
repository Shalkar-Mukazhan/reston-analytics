"""co: writeoff acts — accounts, product groups, acts, items; inventory_preset_id on restaurant

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

_S = "coffee_original"


def upgrade():
    op.add_column("restaurants", sa.Column("inventory_preset_id", sa.String(100), nullable=True), schema=_S)

    op.create_table(
        "co_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_iiko_id", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        schema=_S,
    )

    op.create_table(
        "co_product_groups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("account_id", sa.Integer, sa.ForeignKey(f"{_S}.co_accounts.id", ondelete="SET NULL"), nullable=True),
        schema=_S,
    )

    op.create_table(
        "co_product_group_members",
        sa.Column("group_id", sa.Integer, sa.ForeignKey(f"{_S}.co_product_groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey(f"{_S}.products.id", ondelete="CASCADE"), primary_key=True),
        schema=_S,
    )

    op.create_table(
        "co_writeoff_acts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("restaurant_id", sa.Integer, sa.ForeignKey(f"{_S}.restaurants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("warehouse_id", sa.Integer, sa.ForeignKey(f"{_S}.restaurant_warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("act_date", sa.Date, nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="draft"),
        sa.Column("iiko_doc_ids", sa.JSON, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey(f"{_S}.users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        schema=_S,
    )

    op.create_table(
        "co_writeoff_items",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("act_id", sa.Integer, sa.ForeignKey(f"{_S}.co_writeoff_acts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Integer, sa.ForeignKey(f"{_S}.products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        schema=_S,
    )


def downgrade():
    op.drop_table("co_writeoff_items", schema=_S)
    op.drop_table("co_writeoff_acts", schema=_S)
    op.drop_table("co_product_group_members", schema=_S)
    op.drop_table("co_product_groups", schema=_S)
    op.drop_table("co_accounts", schema=_S)
    op.drop_column("restaurants", "inventory_preset_id", schema=_S)
