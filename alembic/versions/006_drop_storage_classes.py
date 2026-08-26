"""Drop storage_classes table and items.storage_class_id

Removes the StorageClass feature. Items revert to the fixed project
default thresholds (low=0.99, critical=0.5) that COALESCE previously
fell back to for unassigned items.

Revision ID: 006_drop_storage_classes
Revises: 005_uq_item_name_category
Create Date: 2026-08-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '006_drop_storage_classes'
down_revision = '005_uq_item_name_category'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index('ix_items_storage_class_id', table_name='items')
    op.drop_constraint('fk_items_storage_class_id', 'items', type_='foreignkey')
    op.drop_column('items', 'storage_class_id')
    op.drop_table('storage_classes')


def downgrade() -> None:
    op.create_table(
        'storage_classes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('low_threshold', sa.Float(), nullable=False, server_default='0.99'),
        sa.Column('critical_threshold', sa.Float(), nullable=False, server_default='0.5'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.add_column(
        'items',
        sa.Column('storage_class_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_items_storage_class_id',
        'items', 'storage_classes',
        ['storage_class_id'], ['id'],
    )
    op.create_index('ix_items_storage_class_id', 'items', ['storage_class_id'])
