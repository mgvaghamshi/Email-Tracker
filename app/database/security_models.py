"""
Security-related database models for EmailTracker API
"""
import uuid
import secrets
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, JSON, func
)
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from .models import Base
from typing import List, Optional, Dict, Any


class SecurityAuditLog(Base):
    """Security audit log for tracking all security-related events"""
    __tablename__ = "security_audit_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    action = Column(String, nullable=False)  # login, logout, password_change, etc.
    resource_type = Column(String)  # user, campaign, api_key, etc.
    resource_id = Column(String)
    description = Column(Text, nullable=False)
    ip_address = Column(String)
    user_agent = Column(Text)
    success = Column(Boolean, nullable=False, default=True)
    failure_reason = Column(Text)
    security_metadata = Column(JSON)  # Changed from 'metadata' to avoid conflict
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to user
    user = relationship("User", back_populates="security_audit_logs")
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_security_audit_user_id', 'user_id'),
        Index('idx_security_audit_action', 'action'),
        Index('idx_security_audit_created_at', 'created_at'),
        Index('idx_security_audit_success', 'success'),
        Index('idx_security_audit_ip_address', 'ip_address'),
    )


class PasswordResetToken(Base):
    """Password reset tokens for secure password recovery"""
    __tablename__ = "password_reset_tokens"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    token_hash = Column(String, nullable=False)  # Hashed version for security
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship to user
    user = relationship("User", back_populates="password_reset_tokens")
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_password_reset_user_id', 'user_id'),
        Index('idx_password_reset_token_hash', 'token_hash'),
        Index('idx_password_reset_expires_at', 'expires_at'),
    )
    
    @classmethod
    def create_token(cls, user_id: str) -> 'PasswordResetToken':
        """Create a new password reset token"""
        import hashlib
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        
        return cls(
            user_id=user_id,
            token=token,
            token_hash=token_hash,
            expires_at=expires_at
        )


class SecuritySettings(Base):
    """User-specific security settings and preferences"""
    __tablename__ = "security_settings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Two-factor authentication settings
    two_factor_enabled = Column(Boolean, default=False)
    
    # Notification preferences
    login_notifications = Column(Boolean, default=True)
    suspicious_activity_alerts = Column(Boolean, default=True)
    
    # Session management
    session_timeout_hours = Column(Integer, default=24)
    max_concurrent_sessions = Column(Integer, default=5)
    
    # API key rotation
    api_key_rotation_enabled = Column(Boolean, default=False)
    api_key_rotation_days = Column(Integer, default=90)
    
    # Password policy
    require_password_change = Column(Boolean, default=False)
    password_change_days = Column(Integer, default=90)
    last_password_change = Column(DateTime, default=datetime.utcnow)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to user
    user = relationship("User", back_populates="security_settings")
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_security_settings_user_id', 'user_id'),
    )
    
    @classmethod
    def get_or_create_for_user(cls, db_session, user_id: str) -> 'SecuritySettings':
        """Get existing security settings or create default ones for user"""
        settings = db_session.query(cls).filter(cls.user_id == user_id).first()
        if not settings:
            settings = cls(user_id=user_id)
            db_session.add(settings)
            db_session.commit()
        return settings
