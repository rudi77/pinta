"""Quota management enhancement

Revision ID: 003_quota_management_enhancement
Revises: 002_enhanced_document_processing
Create Date: 2025-08-21 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_quota_management_enhancement'
down_revision = '002_enhanced_document_processing'
branch_labels = None
depends_on = None


def upgrade():
    # Create usage_tracking table for detailed analytics
    op.create_table('usage_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('amount', sa.Integer(), nullable=False, default=1),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(op.f('ix_usage_tracking_user_id'), 'usage_tracking', ['user_id'], unique=False)
    op.create_index(op.f('ix_usage_tracking_resource_type'), 'usage_tracking', ['resource_type'], unique=False)
    op.create_index(op.f('ix_usage_tracking_created_at'), 'usage_tracking', ['created_at'], unique=False)
    
    # Create quota_notifications table
    op.create_table('quota_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('threshold_percentage', sa.Float(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, default=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    )
    op.create_index(op.f('ix_quota_notifications_user_id'), 'quota_notifications', ['user_id'], unique=False)
    op.create_index(op.f('ix_quota_notifications_is_read'), 'quota_notifications', ['is_read'], unique=False)
    
    # Add enhanced quota fields to users table
    op.add_column('users', sa.Column('documents_this_month', sa.Integer(), nullable=True, default=0))
    op.add_column('users', sa.Column('api_requests_today', sa.Integer(), nullable=True, default=0))
    op.add_column('users', sa.Column('storage_used_mb', sa.Float(), nullable=True, default=0.0))
    op.add_column('users', sa.Column('last_quota_reset', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('quota_warnings_enabled', sa.Boolean(), nullable=False, default=True))
    op.add_column('users', sa.Column('quota_notification_threshold', sa.Integer(), nullable=False, default=80))
    
    # Add quota tracking to quotes table
    op.add_column('quotes', sa.Column('quota_consumed', sa.Boolean(), nullable=False, default=True))
    op.add_column('quotes', sa.Column('generation_method', sa.String(length=50), nullable=True, default='manual'))
    
    # Add tracking to documents table
    op.add_column('documents', sa.Column('quota_consumed', sa.Boolean(), nullable=False, default=True))


def downgrade():
    # Remove added columns from documents table
    op.drop_column('documents', 'quota_consumed')
    
    # Remove added columns from quotes table
    op.drop_column('quotes', 'generation_method')
    op.drop_column('quotes', 'quota_consumed')
    
    # Remove added columns from users table
    op.drop_column('users', 'quota_notification_threshold')
    op.drop_column('users', 'quota_warnings_enabled')
    op.drop_column('users', 'last_quota_reset')
    op.drop_column('users', 'storage_used_mb')
    op.drop_column('users', 'api_requests_today')
    op.drop_column('users', 'documents_this_month')
    
    # Drop quota_notifications table
    op.drop_index(op.f('ix_quota_notifications_is_read'), table_name='quota_notifications')
    op.drop_index(op.f('ix_quota_notifications_user_id'), table_name='quota_notifications')
    op.drop_table('quota_notifications')
    
    # Drop usage_tracking table
    op.drop_index(op.f('ix_usage_tracking_created_at'), table_name='usage_tracking')
    op.drop_index(op.f('ix_usage_tracking_resource_type'), table_name='usage_tracking')
    op.drop_index(op.f('ix_usage_tracking_user_id'), table_name='usage_tracking')
    op.drop_table('usage_tracking')