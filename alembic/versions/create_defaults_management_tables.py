"""Create defaults management tables

Revision ID: defaults_management_001
Revises: (current latest migration)
Create Date: 2025-08-20 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers
revision = 'defaults_management_001'
down_revision = None  # Update this to your latest migration
branch_labels = None
depends_on = None


def upgrade():
    """Create defaults management tables"""
    
    # Create global_defaults table
    op.create_table(
        'global_defaults',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(50), nullable=False, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'key', name='_global_defaults_category_key')
    )
    
    # Create tenant_defaults table
    op.create_table(
        'tenant_defaults',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=False),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(50), nullable=False, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'category', 'key', name='_tenant_defaults_tenant_category_key')
    )
    
    # Create user_defaults table
    op.create_table(
        'user_defaults',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(100), nullable=False),
        sa.Column('tenant_id', sa.String(100), nullable=True),
        sa.Column('category', sa.String(100), nullable=False),
        sa.Column('key', sa.String(200), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(50), nullable=False, default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'category', 'key', name='_user_defaults_user_category_key')
    )
    
    # Create indexes for performance
    op.create_index('idx_global_defaults_category', 'global_defaults', ['category'])
    op.create_index('idx_global_defaults_category_key', 'global_defaults', ['category', 'key'])
    op.create_index('idx_global_defaults_active', 'global_defaults', ['is_active'])
    
    op.create_index('idx_tenant_defaults_tenant', 'tenant_defaults', ['tenant_id'])
    op.create_index('idx_tenant_defaults_category', 'tenant_defaults', ['category'])
    op.create_index('idx_tenant_defaults_tenant_category', 'tenant_defaults', ['tenant_id', 'category'])
    op.create_index('idx_tenant_defaults_active', 'tenant_defaults', ['is_active'])
    
    op.create_index('idx_user_defaults_user', 'user_defaults', ['user_id'])
    op.create_index('idx_user_defaults_tenant', 'user_defaults', ['tenant_id'])
    op.create_index('idx_user_defaults_category', 'user_defaults', ['category'])
    op.create_index('idx_user_defaults_user_category', 'user_defaults', ['user_id', 'category'])
    op.create_index('idx_user_defaults_active', 'user_defaults', ['is_active'])


def downgrade():
    """Drop defaults management tables"""
    
    # Drop indexes
    op.drop_index('idx_user_defaults_active', 'user_defaults')
    op.drop_index('idx_user_defaults_user_category', 'user_defaults')
    op.drop_index('idx_user_defaults_category', 'user_defaults')
    op.drop_index('idx_user_defaults_tenant', 'user_defaults')
    op.drop_index('idx_user_defaults_user', 'user_defaults')
    
    op.drop_index('idx_tenant_defaults_active', 'tenant_defaults')
    op.drop_index('idx_tenant_defaults_tenant_category', 'tenant_defaults')
    op.drop_index('idx_tenant_defaults_category', 'tenant_defaults')
    op.drop_index('idx_tenant_defaults_tenant', 'tenant_defaults')
    
    op.drop_index('idx_global_defaults_active', 'global_defaults')
    op.drop_index('idx_global_defaults_category_key', 'global_defaults')
    op.drop_index('idx_global_defaults_category', 'global_defaults')
    
    # Drop tables
    op.drop_table('user_defaults')
    op.drop_table('tenant_defaults')
    op.drop_table('global_defaults')
