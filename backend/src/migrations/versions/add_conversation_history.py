"""add conversation history

Revision ID: add_conversation_history
Revises: 
Create Date: 2024-03-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_conversation_history'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_by_ai and conversation_history columns to quotes table
    op.add_column('quotes', sa.Column('created_by_ai', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('quotes', sa.Column('conversation_history', sa.Text(), nullable=True))


def downgrade() -> None:
    # Remove created_by_ai and conversation_history columns from quotes table
    op.drop_column('quotes', 'conversation_history')
    op.drop_column('quotes', 'created_by_ai') 