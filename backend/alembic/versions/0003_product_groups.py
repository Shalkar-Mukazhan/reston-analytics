"""Add product_groups table, refactor catalog and waste_rates

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Создаём таблицу групп
    op.create_table(
        "product_groups",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
    )

    # 2. Заполняем группы из существующих данных
    op.execute("""
        INSERT INTO product_groups (name)
        SELECT DISTINCT group_name FROM product_catalog
        WHERE group_name IS NOT NULL
        ORDER BY group_name
    """)

    # 3. Добавляем FK колонку в product_catalog
    op.add_column("product_catalog", sa.Column("group_id", sa.Integer, nullable=True))
    op.execute("""
        UPDATE product_catalog
        SET group_id = pg.id
        FROM product_groups pg
        WHERE product_catalog.group_name = pg.name
    """)
    op.alter_column("product_catalog", "group_id", nullable=False)
    op.create_foreign_key("fk_catalog_group", "product_catalog", "product_groups", ["group_id"], ["id"])
    op.drop_column("product_catalog", "group_name")

    # 4. Добавляем FK колонку в waste_rates
    op.add_column("waste_rates", sa.Column("group_id", sa.Integer, nullable=True))
    op.execute("""
        UPDATE waste_rates
        SET group_id = pg.id
        FROM product_groups pg
        WHERE waste_rates.group_name = pg.name
    """)
    # Нормы у которых группа не совпала — удаляем (мусорные данные)
    op.execute("DELETE FROM waste_rates WHERE group_id IS NULL")
    op.alter_column("waste_rates", "group_id", nullable=False)
    op.create_foreign_key("fk_rates_group", "waste_rates", "product_groups", ["group_id"], ["id"])

    # 5. Обновляем уникальный constraint в waste_rates
    op.drop_constraint("uq_waste_rate", "waste_rates")
    op.create_unique_constraint("uq_waste_rate", "waste_rates", ["restaurant_id", "group_id"])
    op.drop_column("waste_rates", "group_name")


def downgrade():
    op.add_column("waste_rates", sa.Column("group_name", sa.String(255)))
    op.execute("""
        UPDATE waste_rates
        SET group_name = pg.name
        FROM product_groups pg
        WHERE waste_rates.group_id = pg.id
    """)
    op.drop_constraint("uq_waste_rate", "waste_rates")
    op.drop_constraint("fk_rates_group", "waste_rates", type_="foreignkey")
    op.drop_column("waste_rates", "group_id")
    op.create_unique_constraint("uq_waste_rate", "waste_rates", ["restaurant_id", "group_name"])

    op.add_column("product_catalog", sa.Column("group_name", sa.String(255)))
    op.execute("""
        UPDATE product_catalog
        SET group_name = pg.name
        FROM product_groups pg
        WHERE product_catalog.group_id = pg.id
    """)
    op.drop_constraint("fk_catalog_group", "product_catalog", type_="foreignkey")
    op.drop_column("product_catalog", "group_id")

    op.drop_table("product_groups")
