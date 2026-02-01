"""Add recurring campaigns tables

Revision ID: 3f5e7a9b2c1d
Revises: ac8130488348
Create Date: 2025-01-20 21:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3f5e7a9b2c1d'
down_revision: Union[str, None] = 'ac8130488348'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create recurring campaigns tables"""
    
    # Create recurring_campaigns table
    op.create_table(
        'recurring_campaigns',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='draft'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='false'),
        
        # Campaign content reference
        sa.Column('template_id', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('email_html', sa.Text(), nullable=True),
        sa.Column('email_text', sa.Text(), nullable=True),
        sa.Column('contact_list_ids', sa.Text(), nullable=True),
        
        # Schedule configuration
        sa.Column('frequency', sa.String(), nullable=False),
        sa.Column('custom_interval_days', sa.Integer(), nullable=True),
        sa.Column('send_on_weekdays', sa.Text(), nullable=True),
        sa.Column('send_time', sa.String(), nullable=False),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        
        # Date constraints
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('max_occurrences', sa.Integer(), nullable=True),
        sa.Column('skip_weekends', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('skip_holidays', sa.Boolean(), nullable=False, server_default='false'),
        
        # Tracking
        sa.Column('next_send_at', sa.DateTime(), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.Column('total_occurrences', sa.Integer(), nullable=False, server_default='0'),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('paused_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ondelete='SET NULL'),
    )
    
    # Create recurring_campaign_occurrences table
    op.create_table(
        'recurring_campaign_occurrences',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('recurring_campaign_id', sa.String(), nullable=False),
        sa.Column('sequence_number', sa.Integer(), nullable=False),
        
        # Campaign execution reference
        sa.Column('campaign_id', sa.String(), nullable=True),
        
        # Schedule information
        sa.Column('scheduled_at', sa.DateTime(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        
        # Results tracking
        sa.Column('recipients_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_delivered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_opened', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_clicked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_bounced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('emails_unsubscribed', sa.Integer(), nullable=False, server_default='0'),
        
        # Error tracking
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['recurring_campaign_id'], ['recurring_campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='SET NULL'),
    )
    
    # Create indexes for performance
    op.create_index('idx_recurring_campaigns_user_status', 'recurring_campaigns', ['user_id', 'status'])
    op.create_index('idx_recurring_campaigns_active', 'recurring_campaigns', ['is_active', 'next_send_at'])
    op.create_index('idx_recurring_campaigns_next_send', 'recurring_campaigns', ['next_send_at'])
    
    op.create_index('idx_recurring_occurrences_campaign', 'recurring_campaign_occurrences', ['recurring_campaign_id'])
    op.create_index('idx_recurring_occurrences_schedule', 'recurring_campaign_occurrences', ['scheduled_at', 'status'])
    op.create_index('idx_recurring_occurrences_status', 'recurring_campaign_occurrences', ['status', 'scheduled_at'])


def downgrade() -> None:
    """Drop recurring campaigns tables"""
    
    # Drop indexes
    op.drop_index('idx_recurring_occurrences_status', 'recurring_campaign_occurrences')
    op.drop_index('idx_recurring_occurrences_schedule', 'recurring_campaign_occurrences')
    op.drop_index('idx_recurring_occurrences_campaign', 'recurring_campaign_occurrences')
    
    op.drop_index('idx_recurring_campaigns_next_send', 'recurring_campaigns')
    op.drop_index('idx_recurring_campaigns_active', 'recurring_campaigns')
    op.drop_index('idx_recurring_campaigns_user_status', 'recurring_campaigns')
    
    # Drop tables
    op.drop_table('recurring_campaign_occurrences')
    op.drop_table('recurring_campaigns')
