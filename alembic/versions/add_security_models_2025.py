"""Add security management models

Revision ID: add_security_models_2025
Revises: b54e3a8fd87c
Create Date: 2025-01-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'add_security_models_2025'
down_revision: Union[str, None] = '4ee9c3d1d35a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    # Check if tables exist before creating them
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    existing_tables = inspector.get_table_names()
    
    # Create security_audit_logs table (if it doesn't exist)
    if 'security_audit_logs' not in existing_tables:
        op.create_table('security_audit_logs',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('action', sa.String(), nullable=False),
            sa.Column('resource_type', sa.String(), nullable=True),
            sa.Column('resource_id', sa.String(), nullable=True),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('ip_address', sa.String(), nullable=True),
            sa.Column('user_agent', sa.Text(), nullable=True),
            sa.Column('success', sa.Boolean(), nullable=False, default=True),
            sa.Column('failure_reason', sa.Text(), nullable=True),
            sa.Column('security_metadata', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id')
        )
        
        # Create indexes for security_audit_logs
        op.create_index('idx_security_audit_user_id', 'security_audit_logs', ['user_id'], unique=False)
        op.create_index('idx_security_audit_action', 'security_audit_logs', ['action'], unique=False)
        op.create_index('idx_security_audit_created_at', 'security_audit_logs', ['created_at'], unique=False)
        op.create_index('idx_security_audit_success', 'security_audit_logs', ['success'], unique=False)
        op.create_index('idx_security_audit_ip_address', 'security_audit_logs', ['ip_address'], unique=False)

    # Create password_reset_tokens table (if it doesn't exist)
    if 'password_reset_tokens' not in existing_tables:
        op.create_table('password_reset_tokens',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('token', sa.String(), nullable=False),
            sa.Column('token_hash', sa.String(), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token')
        )
        
        # Create indexes for password_reset_tokens
        op.create_index('idx_password_reset_user_id', 'password_reset_tokens', ['user_id'], unique=False)
        op.create_index('idx_password_reset_token_hash', 'password_reset_tokens', ['token_hash'], unique=False)
        op.create_index('idx_password_reset_expires_at', 'password_reset_tokens', ['expires_at'], unique=False)

    # Create security_settings table (if it doesn't exist)  
    if 'security_settings' not in existing_tables:
        op.create_table('security_settings',
            sa.Column('id', sa.String(), nullable=False),
            sa.Column('user_id', sa.String(), nullable=False),
            sa.Column('two_factor_enabled', sa.Boolean(), nullable=True, default=False),
            sa.Column('login_notifications', sa.Boolean(), nullable=True, default=True),
            sa.Column('suspicious_activity_alerts', sa.Boolean(), nullable=True, default=True),
            sa.Column('session_timeout_hours', sa.Integer(), nullable=True, default=24),
            sa.Column('max_concurrent_sessions', sa.Integer(), nullable=True, default=5),
            sa.Column('api_key_rotation_enabled', sa.Boolean(), nullable=True, default=False),
            sa.Column('api_key_rotation_days', sa.Integer(), nullable=True, default=90),
            sa.Column('require_password_change', sa.Boolean(), nullable=True, default=False),
            sa.Column('password_change_days', sa.Integer(), nullable=True, default=90),
            sa.Column('last_password_change', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.Column('updated_at', sa.DateTime(), nullable=True, default=sa.text('CURRENT_TIMESTAMP')),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id')
        )
        
        # Create indexes for security_settings
        op.create_index('idx_security_settings_user_id', 'security_settings', ['user_id'], unique=False)


def downgrade():
    # Drop tables and indexes in reverse order
    op.drop_index('idx_security_settings_user_id', table_name='security_settings')
    op.drop_table('security_settings')
    
    op.drop_index('idx_password_reset_expires_at', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_token_hash', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_user_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
    
    op.drop_index('idx_security_audit_ip_address', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_success', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_created_at', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_action', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_user_id', table_name='security_audit_logs')
    op.drop_table('security_audit_logs')

    # Create security_audit_logs table
    op.create_table('security_audit_logs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for security_audit_logs
    op.create_index('idx_audit_user_id', 'security_audit_logs', ['user_id'], unique=False)
    op.create_index('idx_audit_action', 'security_audit_logs', ['action'], unique=False)
    op.create_index('idx_audit_timestamp', 'security_audit_logs', ['timestamp'], unique=False)
    op.create_index('idx_audit_success', 'security_audit_logs', ['success'], unique=False)
    op.create_index('idx_audit_resource', 'security_audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('idx_audit_ip_address', 'security_audit_logs', ['ip_address'], unique=False)

    # Create password_reset_tokens table
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('token', sa.String(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('is_used', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('token')
    )
    
    # Create indexes for password_reset_tokens
    op.create_index('idx_reset_token_user_id', 'password_reset_tokens', ['user_id'], unique=False)
    op.create_index('idx_reset_token', 'password_reset_tokens', ['token'], unique=False)
    op.create_index('idx_reset_expires_at', 'password_reset_tokens', ['expires_at'], unique=False)
    op.create_index('idx_reset_is_used', 'password_reset_tokens', ['is_used'], unique=False)

    # Create login_attempts table
    op.create_table('login_attempts',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('failure_reason', sa.String(), nullable=True),
        sa.Column('ip_address', sa.String(), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=True),
        sa.Column('requires_2fa', sa.Boolean(), nullable=True),
        sa.Column('two_factor_completed', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for login_attempts
    op.create_index('idx_login_user_id', 'login_attempts', ['user_id'], unique=False)
    op.create_index('idx_login_email', 'login_attempts', ['email'], unique=False)
    op.create_index('idx_login_attempted_at', 'login_attempts', ['attempted_at'], unique=False)
    op.create_index('idx_login_success', 'login_attempts', ['success'], unique=False)
    op.create_index('idx_login_ip_address', 'login_attempts', ['ip_address'], unique=False)
    op.create_index('idx_login_requires_2fa', 'login_attempts', ['requires_2fa'], unique=False)

    # Create security_settings table
    op.create_table('security_settings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('two_factor_enabled', sa.Boolean(), nullable=True),
        sa.Column('session_timeout_hours', sa.Integer(), nullable=True),
        sa.Column('max_concurrent_sessions', sa.Integer(), nullable=True),
        sa.Column('login_notifications', sa.Boolean(), nullable=True),
        sa.Column('suspicious_activity_alerts', sa.Boolean(), nullable=True),
        sa.Column('api_key_rotation_enabled', sa.Boolean(), nullable=True),
        sa.Column('api_key_rotation_days', sa.Integer(), nullable=True),
        sa.Column('require_password_change', sa.Boolean(), nullable=True),
        sa.Column('password_change_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create indexes for security_settings
    op.create_index('idx_security_user_id', 'security_settings', ['user_id'], unique=False)
    op.create_index('idx_security_2fa_enabled', 'security_settings', ['two_factor_enabled'], unique=False)
    op.create_index('idx_security_api_rotation', 'security_settings', ['api_key_rotation_enabled'], unique=False)


def downgrade():
    # Drop indexes and tables in reverse order
    op.drop_index('idx_security_api_rotation', table_name='security_settings')
    op.drop_index('idx_security_2fa_enabled', table_name='security_settings')
    op.drop_index('idx_security_user_id', table_name='security_settings')
    op.drop_table('security_settings')

    op.drop_index('idx_login_requires_2fa', table_name='login_attempts')
    op.drop_index('idx_login_ip_address', table_name='login_attempts')
    op.drop_index('idx_login_success', table_name='login_attempts')
    op.drop_index('idx_login_attempted_at', table_name='login_attempts')
    op.drop_index('idx_login_email', table_name='login_attempts')
    op.drop_index('idx_login_user_id', table_name='login_attempts')
    op.drop_table('login_attempts')

    op.drop_index('idx_reset_is_used', table_name='password_reset_tokens')
    op.drop_index('idx_reset_expires_at', table_name='password_reset_tokens')
    op.drop_index('idx_reset_token', table_name='password_reset_tokens')
    op.drop_index('idx_reset_token_user_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')

    op.drop_index('idx_audit_ip_address', table_name='security_audit_logs')
    op.drop_index('idx_audit_resource', table_name='security_audit_logs')
    op.drop_index('idx_audit_success', table_name='security_audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='security_audit_logs')
    op.drop_index('idx_audit_action', table_name='security_audit_logs')
    op.drop_index('idx_audit_user_id', table_name='security_audit_logs')
    op.drop_table('security_audit_logs')

    op.drop_index('idx_session_last_activity', table_name='user_sessions')
    op.drop_index('idx_session_active', table_name='user_sessions')
    op.drop_index('idx_session_expires_at', table_name='user_sessions')
    op.drop_index('idx_session_token', table_name='user_sessions')
    op.drop_index('idx_session_user_id', table_name='user_sessions')
    op.drop_table('user_sessions')
