"""Drop display_order from categories

Revision ID: 002_drop_display_order
Revises: 001_initial
Create Date: 2026-03-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_drop_display_order'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('categories', 'display_order')


def downgrade() -> None:
    op.add_column(
        'categories',
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0')
    )
