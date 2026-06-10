"""Add unique constraint on (name, category_id) in items

Prevents duplicate item names within the same category. The router
already returns 409 on IntegrityError for this case; the constraint
makes it actually enforceable at the database level.

Revision ID: 005_unique_item_name_per_category
Revises: 004_item_id_bigint
Create Date: 2026-06-10 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '005_unique_item_name_per_category'
down_revision = '004_item_id_bigint'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        'uq_items_name_category',
        'items',
        ['name', 'category_id'],
    )


def downgrade() -> None:
    op.drop_constraint('uq_items_name_category', 'items', type_='unique')
