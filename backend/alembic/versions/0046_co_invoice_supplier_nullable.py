"""co: make invoice supplier_id nullable (suppliers created from iiko only)

Revision ID: 0046
Revises: 0045
Create Date: 2026-05-05
"""

from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade():
    # Allow NULL supplier_id on invoices — supplier should come from iiko sync,
    # not be auto-created during OCR scanning
    op.alter_column(
        "invoices",
        "supplier_id",
        nullable=True,
        schema="coffee_original",
    )


def downgrade():
    op.alter_column(
        "invoices",
        "supplier_id",
        nullable=False,
        schema="coffee_original",
    )
