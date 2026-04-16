"""Add material_prices table for RAG-powered quote grounding

Revision ID: 005_add_material_prices
Revises: 004_add_user_cost_parameters
Create Date: 2026-04-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = '005_add_material_prices'
down_revision = '004_add_user_cost_parameters'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'material_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('manufacturer', sa.String(length=120), nullable=True),
        sa.Column('category', sa.String(length=80), nullable=True),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('price_net', sa.Float(), nullable=False),
        sa.Column('region', sa.String(length=20), nullable=True),
        sa.Column('source', sa.String(length=120), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_material_prices_name', 'material_prices', ['name'])
    op.create_index('ix_material_prices_category', 'material_prices', ['category'])
    op.create_index('ix_material_prices_region', 'material_prices', ['region'])


def downgrade() -> None:
    op.drop_index('ix_material_prices_region', table_name='material_prices')
    op.drop_index('ix_material_prices_category', table_name='material_prices')
    op.drop_index('ix_material_prices_name', table_name='material_prices')
    op.drop_table('material_prices')
