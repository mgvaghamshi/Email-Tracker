"""Add unified campaign send_type fields

Revision ID: unified_campaign_001
Revises: 7bcd3e391bc1
Create Date: 2025-01-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'unified_campaign_001'
down_revision = '7bcd3e391bc1'
branch_labels = None
depends_on = None


def upgrade():
    """Add unified campaign fields for send_type and parent/child tracking"""
    
    # Add new columns to campaigns table
    op.add_column('campaigns', sa.Column('send_type', sa.String(length=20), nullable=False, server_default='immediate'))
    op.add_column('campaigns', sa.Column('parent_campaign_id', sa.String(), nullable=True))
    op.add_column('campaigns', sa.Column('recurring_campaign_id', sa.String(), nullable=True))
    op.add_column('campaigns', sa.Column('sequence_number', sa.Integer(), nullable=True))
    op.add_column('campaigns', sa.Column('next_send_at', sa.DateTime(), nullable=True))
    
    # Create indexes for performance
    op.create_index('idx_campaign_send_type', 'campaigns', ['send_type'], unique=False)
    op.create_index('idx_campaign_parent_id', 'campaigns', ['parent_campaign_id'], unique=False)
    op.create_index('idx_campaign_recurring_id', 'campaigns', ['recurring_campaign_id'], unique=False)
    op.create_index('idx_campaign_next_send', 'campaigns', ['next_send_at'], unique=False)
    op.create_index('idx_campaign_sequence', 'campaigns', ['parent_campaign_id', 'sequence_number'], unique=False)
    
    # Create foreign key for parent campaign relationship
    op.create_foreign_key('fk_campaign_parent', 'campaigns', 'campaigns', ['parent_campaign_id'], ['id'])


def downgrade():
    """Remove unified campaign fields"""
    
    # Drop foreign key and indexes
    op.drop_constraint('fk_campaign_parent', 'campaigns', type_='foreignkey')
    op.drop_index('idx_campaign_sequence', table_name='campaigns')
    op.drop_index('idx_campaign_next_send', table_name='campaigns')
    op.drop_index('idx_campaign_recurring_id', table_name='campaigns')
    op.drop_index('idx_campaign_parent_id', table_name='campaigns')
    op.drop_index('idx_campaign_send_type', table_name='campaigns')
    
    # Drop columns
    op.drop_column('campaigns', 'next_send_at')
    op.drop_column('campaigns', 'sequence_number')
    op.drop_column('campaigns', 'recurring_campaign_id')
    op.drop_column('campaigns', 'parent_campaign_id')
    op.drop_column('campaigns', 'send_type')
