"""Unified agent schema: Conversation, ConversationMessage, ChannelLink.

Revision ID: 006_unified_agent_schema
Revises: 005_add_material_prices
Create Date: 2026-05-03 00:00:00.000000

Stage 1 of the Web/Telegram unification: persists the agent conversation
in the central Pinta DB (not in the bot's local FS) and lets multiple
channel identities (telegram chat_id, future teams id, etc.) point at the
same Pinta user.
"""
from alembic import op
import sqlalchemy as sa


revision = '006_unified_agent_schema'
down_revision = '005_add_material_prices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations ────────────────────────────────────────────────────
    op.create_table(
        'conversations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False, server_default='web'),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversations_user_id', 'conversations', ['user_id'])
    op.create_index('ix_conversations_is_active', 'conversations', ['is_active'])

    # ── conversation_messages ────────────────────────────────────────────
    op.create_table(
        'conversation_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('conversation_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('extra_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_conversation_messages_conversation_id',
                    'conversation_messages', ['conversation_id'])

    # ── channel_links ────────────────────────────────────────────────────
    op.create_table(
        'channel_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('channel', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=128), nullable=False),
        sa.Column('display_name', sa.String(length=120), nullable=True),
        sa.Column('linking_token', sa.String(length=64), nullable=True),
        sa.Column('linking_token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_anonymous_shadow', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('linking_token', name='uq_channel_links_linking_token'),
        sa.UniqueConstraint('channel', 'external_id', name='uq_channel_external_per_channel'),
    )
    op.create_index('ix_channel_links_user_id', 'channel_links', ['user_id'])
    op.create_index('ix_channel_links_channel', 'channel_links', ['channel'])
    op.create_index('ix_channel_links_external_id', 'channel_links', ['external_id'])


def downgrade() -> None:
    op.drop_index('ix_channel_links_external_id', table_name='channel_links')
    op.drop_index('ix_channel_links_channel', table_name='channel_links')
    op.drop_index('ix_channel_links_user_id', table_name='channel_links')
    op.drop_table('channel_links')

    op.drop_index('ix_conversation_messages_conversation_id',
                  table_name='conversation_messages')
    op.drop_table('conversation_messages')

    op.drop_index('ix_conversations_is_active', table_name='conversations')
    op.drop_index('ix_conversations_user_id', table_name='conversations')
    op.drop_table('conversations')
