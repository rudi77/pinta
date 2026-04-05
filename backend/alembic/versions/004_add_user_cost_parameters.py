"""Add user cost parameters (hourly_rate, material_cost_markup)

Revision ID: 004_add_user_cost_parameters
Revises: 003_quota_management_enhancement
Create Date: 2026-04-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_add_user_cost_parameters'
down_revision = '003_quota_management_enhancement'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('hourly_rate', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('material_cost_markup', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'material_cost_markup')
    op.drop_column('users', 'hourly_rate')
