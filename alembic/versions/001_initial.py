"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-02-21 21:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Create items table
    op.create_table(
        'items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=False),
        sa.Column('current_quantity', sa.Float(), nullable=False, server_default='0'),
        sa.Column('par_level', sa.Float(), nullable=False, server_default='0'),
        sa.Column('category_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('ix_items_category_id', 'items', ['category_id'])
    op.create_index('ix_items_name', 'items', ['name'])


def downgrade() -> None:
    op.drop_index('ix_items_name', table_name='items')
    op.drop_index('ix_items_category_id', table_name='items')
    op.drop_table('items')
    op.drop_table('categories')
