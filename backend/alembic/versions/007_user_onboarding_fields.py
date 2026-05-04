"""Add user onboarding fields (vat_id, logo_path, onboarding_completed_at).

Revision ID: 007_user_onboarding_fields
Revises: 006_unified_agent_schema
Create Date: 2026-05-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '007_user_onboarding_fields'
down_revision = '006_unified_agent_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('vat_id', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('logo_path', sa.String(length=500), nullable=True))
    op.add_column('users', sa.Column('onboarding_completed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'onboarding_completed_at')
    op.drop_column('users', 'logo_path')
    op.drop_column('users', 'vat_id')
