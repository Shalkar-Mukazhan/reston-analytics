"""Add accounts table and link to product_groups

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-29
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Создаём таблицу счетов списания IIKO
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_iiko_id", sa.String(100), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )

    # 2. Добавляем FK в product_groups
    op.add_column("product_groups",
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), nullable=True)
    )

    # 3. Заполняем уникальные счета из settings_writeoff данных
    op.execute("""
        INSERT INTO accounts (account_iiko_id, name) VALUES
        ('d2ccc4b7-dac4-4800-afa3-ad58ed24c135', 'Списание сырой продукции (Raw waste)'),
        ('7bd3df7b-f5ac-4171-abcf-7ead57b1e8dc', 'Списание упаковочных материалов (Raw waste)'),
        ('312ad44d-1b11-4693-af73-40152224cdce', 'PDP расходы промо (ресторан)'),
        ('54b7c51e-ed08-40bc-8175-6546e16da205', 'Расходы на покупку хозяйственного инвентаря (ресторан)'),
        ('7d51e974-1aa7-4acd-8454-60643ca8c018', 'Расходы на покупку химии (ресторан)'),
        ('69e99c59-b7b8-49db-8c30-180bdef4c14d', 'Запчасти для ремонта оборудования ресторанов'),
        ('17a9d443-3096-40fb-b962-2524ed536909', 'Расходы на приобретение кухонного инвентаря (ресторан)'),
        ('0ea87879-f202-4863-a08d-dd7f9fa27928', 'Расходы на покупку бумаги для кассовых аппаратов'),
        ('3ef2a1ce-693a-4a4c-9fef-6e6ffcd9c6ef', 'Упаковочные материалы (84ХХ)'),
        ('437e3da8-e3ca-4729-ae96-de8c649e193d', 'Полуфабрикаты (84ХХ)')
    """)

    # 4. Привязываем группы к счетам
    mappings = [
        (['Булки', 'Соусы, топпинги и сиропы', 'Мясные полуфабрикаты',
          'Пирожки', 'Молочные смеси', 'Другие продукты', 'Продукты Кафе'],
         'd2ccc4b7-dac4-4800-afa3-ad58ed24c135'),
        (['Упаковка'], '7bd3df7b-f5ac-4171-abcf-7ead57b1e8dc'),
        (['PDP  расходы на промо (ресторан)'], '312ad44d-1b11-4693-af73-40152224cdce'),
        (['Расходы на покупку хозяйственного инвентаря (ресторан)'], '54b7c51e-ed08-40bc-8175-6546e16da205'),
        (['Расходы на покупку химии (ресторан)'], '7d51e974-1aa7-4acd-8454-60643ca8c018'),
        (['Запчасти для ремонта оборудования ресторанов'], '69e99c59-b7b8-49db-8c30-180bdef4c14d'),
        (['Расходы на приобретение кухонного инвентаря (ресторан)',
          'Расходы на приобретение кухонного инвентаря (ресторан);'],
         '17a9d443-3096-40fb-b962-2524ed536909'),
        (['Расходы на покупку бумаги для кассовых аппаратов'], '0ea87879-f202-4863-a08d-dd7f9fa27928'),
        (['Упаковочные материалы (84ХХ) ', 'Упаковочные материалы (84ХХ)'], '3ef2a1ce-693a-4a4c-9fef-6e6ffcd9c6ef'),
        (['Полуфабрикаты (84ХХ) ', 'Полуфабрикаты (84ХХ)'], '437e3da8-e3ca-4729-ae96-de8c649e193d'),
    ]

    for groups, account_uuid in mappings:
        for group_name in groups:
            op.execute(f"""
                UPDATE product_groups
                SET account_id = (SELECT id FROM accounts WHERE account_iiko_id = '{account_uuid}')
                WHERE name = '{group_name.replace("'", "''")}'
            """)


def downgrade():
    op.drop_column("product_groups", "account_id")
    op.drop_table("accounts")
