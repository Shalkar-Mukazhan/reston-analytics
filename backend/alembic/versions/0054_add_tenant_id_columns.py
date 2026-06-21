"""co: add tenant_id to all existing tables (multi-tenancy step 2)

Adds nullable tenant_id FK -> tenants, backfills existing rows to tenant_id=1
(Coffee Original), and indexes tenant_id. NOT NULL / composite uniques come later.

Revision ID: 0054_add_tenant_id_columns
Revises: 0053_add_tenants_table
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_add_tenant_id_columns"
down_revision = "0053_add_tenants_table"
branch_labels = None
depends_on = None

_S = "coffee_original"

# tables that get tenant_id, in FK-safe order
tables = [
    "users",
    "restaurants",
    "suppliers",
    "products",
    "co_accounts",
    "warehouse_types",
    "co_product_groups",
    "co_settings",
]

# co_settings excluded: tenant_id will become part of a composite PK later
index_tables = [
    "users",
    "restaurants",
    "suppliers",
    "products",
    "co_accounts",
    "warehouse_types",
    "co_product_groups",
]


def upgrade():
    # ЧАСТЬ А — добавить колонку tenant_id (nullable пока)
    for table in tables:
        op.add_column(
            table,
            sa.Column(
                "tenant_id",
                sa.Integer,
                sa.ForeignKey("coffee_original.tenants.id"),
                nullable=True,
            ),
            schema=_S,
        )

    # ЧАСТЬ Б — backfill существующих строк tenant_id = 1
    for table in tables:
        op.execute(
            f"UPDATE coffee_original.{table} SET tenant_id = 1 WHERE tenant_id IS NULL"
        )

    # ЧАСТЬ В — индексы на tenant_id
    for table in index_tables:
        op.create_index(
            f"ix_{table}_tenant_id",
            table,
            ["tenant_id"],
            schema=_S,
        )


def downgrade():
    for table in reversed(index_tables):
        op.drop_index(f"ix_{table}_tenant_id", table_name=table, schema=_S)
    for table in reversed(tables):
        op.drop_column(table, "tenant_id", schema=_S)
