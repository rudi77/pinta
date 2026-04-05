"""add is_paid column to quotes table

Revision ID: add_quote_is_paid
Revises: add_conversation_history
Create Date: 2026-04-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_quote_is_paid'
down_revision: Union[str, None] = 'add_conversation_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quotes', sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('quotes', 'is_paid')
