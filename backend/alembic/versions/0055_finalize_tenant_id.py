"""co: finalize tenant_id — NOT NULL + composite uniques + co_settings PK (step 3)

Last DDL migration of the tenant_id rollout. tenant_id is fully backfilled
(see 0054), so NOT NULL is safe. Global uniques become composite with tenant_id,
and co_settings primary key becomes (tenant_id, key).

Revision ID: 0055_finalize_tenant_id
Revises: 0054_add_tenant_id_columns
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0055_finalize_tenant_id"
down_revision = "0054_add_tenant_id_columns"
branch_labels = None
depends_on = None

_S = "coffee_original"

tables_with_tenant = [
    "users", "restaurants", "suppliers", "products",
    "co_accounts", "warehouse_types", "co_product_groups", "co_settings",
]


def upgrade():
    # === ЧАСТЬ А: NOT NULL на tenant_id (backfill сделан в 0054 — safe) ===
    for table in tables_with_tenant:
        op.alter_column(table, "tenant_id",
                        existing_type=sa.Integer,
                        nullable=False,
                        schema=_S)

    # === ЧАСТЬ Б: DROP старые UNIQUE + CREATE составные с tenant_id ===

    # users.email -> (tenant_id, email)
    op.drop_constraint("users_email_key", "users", schema=_S, type_="unique")
    op.create_unique_constraint(
        "uq_users_tenant_email", "users",
        ["tenant_id", "email"], schema=_S)

    # restaurants.code -> (tenant_id, code)
    op.drop_constraint("restaurants_code_key", "restaurants", schema=_S, type_="unique")
    op.create_unique_constraint(
        "uq_restaurants_tenant_code", "restaurants",
        ["tenant_id", "code"], schema=_S)

    # suppliers.iiko_id -> (tenant_id, iiko_id)
    op.drop_constraint("uq_co_suppliers_iiko_id", "suppliers", schema=_S, type_="unique")
    op.create_unique_constraint(
        "uq_suppliers_tenant_iiko_id", "suppliers",
        ["tenant_id", "iiko_id"], schema=_S)

    # products.iiko_article_id -> (tenant_id, iiko_article_id)
    op.drop_constraint("uq_co_products_iiko_article_id", "products", schema=_S, type_="unique")
    op.create_unique_constraint(
        "uq_products_tenant_iiko_article_id", "products",
        ["tenant_id", "iiko_article_id"], schema=_S)

    # co_accounts.account_iiko_id -> (tenant_id, account_iiko_id)
    # реальное имя констрейнта в БД: co_accounts_account_iiko_id_key
    op.drop_constraint("co_accounts_account_iiko_id_key", "co_accounts", schema=_S, type_="unique")
    op.create_unique_constraint(
        "uq_co_accounts_tenant_account_iiko_id", "co_accounts",
        ["tenant_id", "account_iiko_id"], schema=_S)

    # === ЧАСТЬ В: PK co_settings: key -> (tenant_id, key) ===
    op.drop_constraint("co_settings_pkey", "co_settings", schema=_S, type_="primary")
    op.create_primary_key(
        "co_settings_pkey", "co_settings",
        ["tenant_id", "key"], schema=_S)


def downgrade():
    # Восстановить PK co_settings
    op.drop_constraint("co_settings_pkey", "co_settings", schema=_S, type_="primary")
    op.create_primary_key("co_settings_pkey", "co_settings", ["key"], schema=_S)

    # Восстановить одиночные UNIQUE (исходные имена)
    op.drop_constraint("uq_co_accounts_tenant_account_iiko_id", "co_accounts", schema=_S, type_="unique")
    op.create_unique_constraint("co_accounts_account_iiko_id_key", "co_accounts", ["account_iiko_id"], schema=_S)
    op.drop_constraint("uq_products_tenant_iiko_article_id", "products", schema=_S, type_="unique")
    op.create_unique_constraint("uq_co_products_iiko_article_id", "products", ["iiko_article_id"], schema=_S)
    op.drop_constraint("uq_suppliers_tenant_iiko_id", "suppliers", schema=_S, type_="unique")
    op.create_unique_constraint("uq_co_suppliers_iiko_id", "suppliers", ["iiko_id"], schema=_S)
    op.drop_constraint("uq_restaurants_tenant_code", "restaurants", schema=_S, type_="unique")
    op.create_unique_constraint("restaurants_code_key", "restaurants", ["code"], schema=_S)
    op.drop_constraint("uq_users_tenant_email", "users", schema=_S, type_="unique")
    op.create_unique_constraint("users_email_key", "users", ["email"], schema=_S)

    # NOT NULL -> nullable
    for table in reversed(tables_with_tenant):
        op.alter_column(table, "tenant_id",
                        existing_type=sa.Integer,
                        nullable=True,
                        schema=_S)
