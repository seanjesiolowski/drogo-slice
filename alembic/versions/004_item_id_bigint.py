"""Widen items.id from INTEGER to BIGINT

Item ids are QR label numbers and can hold large values (e.g. scanned
12-digit barcodes) that exceed the 32-bit INTEGER range and caused
OverflowError -> 500 on lookup. Widen to BIGINT (64-bit).

Revision ID: 004_item_id_bigint
Revises: 003_add_storage_classes
Create Date: 2026-06-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '004_item_id_bigint'
down_revision = '003_add_storage_classes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'items', 'id',
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'items', 'id',
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
