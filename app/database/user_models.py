"""
User management models for EmailTracker API
"""
import uuid
import secrets
import bcrypt
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, JSON, func, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime
from .models import Base
from typing import List, Optional


class User(Base):
    """User model for authentication and profile management"""
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Authentication fields
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    
    # Profile fields
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    full_name = Column(String, nullable=True)  # Computed field
    avatar_url = Column(String, nullable=True)
    
    # Status and verification
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    is_superuser = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    
    # Security fields
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    password_changed_at = Column(DateTime, default=datetime.utcnow)
    
    # Metadata
    timezone = Column(String, default="UTC")
    locale = Column(String, default="en")
    preferences = Column(Text, nullable=True)  # JSON for user preferences
    
    # Relationships
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    
    # Core entity relationships for data isolation
    campaigns = relationship("Campaign", back_populates="user", cascade="all, delete-orphan")
    email_trackers = relationship("EmailTracker", back_populates="user", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="user", cascade="all, delete-orphan")
    templates = relationship("Template", back_populates="user", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_active', 'is_active'),
        Index('idx_user_verified', 'is_verified'),
        Index('idx_user_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class UserSession(Base):
    """User session model for JWT token management"""
    __tablename__ = "user_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Token information
    access_token_jti = Column(String, unique=True, nullable=False)  # JWT ID for access token
    refresh_token_jti = Column(String, unique=True, nullable=False)  # JWT ID for refresh token
    
    # Session metadata
    device_info = Column(Text, nullable=True)  # JSON with device information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    location = Column(String, nullable=True)  # City, Country
    
    # Status and timing
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String, nullable=True)  # logout, security, admin, expired
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    __table_args__ = (
        Index('idx_session_user_id', 'user_id'),
        Index('idx_session_access_token', 'access_token_jti'),
        Index('idx_session_refresh_token', 'refresh_token_jti'),
        Index('idx_session_active', 'is_active'),
        Index('idx_session_expires_at', 'expires_at'),
    )


class PasswordReset(Base):
    """Password reset token model"""
    __tablename__ = "password_resets"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Token information
    token_hash = Column(String, unique=True, nullable=False)
    
    # Status and timing
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    
    # Request metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="password_resets")
    
    __table_args__ = (
        Index('idx_password_reset_user_id', 'user_id'),
        Index('idx_password_reset_token', 'token_hash'),
        Index('idx_password_reset_expires_at', 'expires_at'),
    )


class EmailVerification(Base):
    """Email verification token model"""
    __tablename__ = "email_verifications"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Token information
    token_hash = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)  # Email being verified
    
    # Status and timing
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    
    # Request metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="email_verifications")
    
    __table_args__ = (
        Index('idx_email_verification_user_id', 'user_id'),
        Index('idx_email_verification_token', 'token_hash'),
        Index('idx_email_verification_email', 'email'),
        Index('idx_email_verification_expires_at', 'expires_at'),
    )


class Role(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Role details
    name = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Permissions (JSON array of permission strings)
    permissions = Column(Text, nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_role_name', 'name'),
        Index('idx_role_active', 'is_active'),
    )
    
    @property
    def permissions_list(self) -> List[str]:
        """Return permissions as a list"""
        if self.permissions:
            import json
            return json.loads(self.permissions)
        return []
    
    @permissions_list.setter
    def permissions_list(self, value: List[str]):
        """Set permissions from a list"""
        if value:
            import json
            self.permissions = json.dumps(value)
        else:
            self.permissions = None

    def __repr__(self):
        return f"<Role(id={self.id}, name={self.name})>"


class UserRole(Base):
    """User-Role association model"""
    __tablename__ = "user_roles"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role_id = Column(String, ForeignKey("roles.id"), nullable=False)
    
    # Assignment metadata
    assigned_by = Column(String, nullable=True)  # User ID who assigned this role
    assigned_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # Optional role expiration
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'role_id', name='uix_user_role'),
        Index('idx_user_role_user_id', 'user_id'),
        Index('idx_user_role_role_id', 'role_id'),
        Index('idx_user_role_active', 'is_active'),
    )


class LoginAttempt(Base):
    """Login attempt tracking for security"""
    __tablename__ = "login_attempts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Attempt details
    email = Column(String, nullable=False, index=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Result
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String, nullable=True)  # invalid_password, account_locked, etc.
    
    # Timing
    attempted_at = Column(DateTime, default=datetime.utcnow)
    
    # Associated user (if found)
    user_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    __table_args__ = (
        Index('idx_login_attempt_email', 'email'),
        Index('idx_login_attempt_ip', 'ip_address'),
        Index('idx_login_attempt_success', 'success'),
        Index('idx_login_attempt_attempted_at', 'attempted_at'),
    )


# ============================================
# Enhanced API Key Models (Secure, User-Based)
# ============================================

class ApiKey(Base):
    """Enhanced API Key model with user-based scoping and security"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Required user association
    
    # Key information
    name = Column(String, nullable=False)  # Friendly name for the key
    hashed_key = Column(String, nullable=False, unique=True, index=True)  # bcrypt hashed key
    prefix = Column(String, nullable=False)  # First 8 chars for identification (emt_xxxxxxxx)
    
    # Scopes and permissions (stored as JSON string)
    scopes = Column(Text, nullable=False, default='[]')  # JSON: ['emails:send', 'campaigns:read', etc.]
    
    # Status and lifecycle
    is_active = Column(Boolean, default=True, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String, nullable=True)
    
    # Rate limiting
    requests_per_minute = Column(Integer, default=100, nullable=False)
    requests_per_day = Column(Integer, default=10000, nullable=False)
    
    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Expiration
    expires_at = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)  # User ID who created this key
    
    # Relationships
    user = relationship("User", back_populates="api_keys")
    usage_records = relationship("ApiKeyUsage", back_populates="api_key", cascade="all, delete-orphan")
    
    # Properties for scope handling
    @property
    def scope_list(self) -> List[str]:
        """Get scopes as a list"""
        if self.scopes:
            try:
                import json
                return json.loads(self.scopes)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @scope_list.setter
    def scope_list(self, value: List[str]):
        """Set scopes from a list"""
        import json
        self.scopes = json.dumps(value) if value else '[]'
    
    def has_scope(self, scope: str) -> bool:
        """Check if API key has a specific scope"""
        return scope in self.scope_list
    
    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if API key has any of the specified scopes"""
        key_scopes = self.scope_list
        return any(scope in key_scopes for scope in scopes)
    
    def has_all_scopes(self, scopes: List[str]) -> bool:
        """Check if API key has all of the specified scopes"""
        key_scopes = self.scope_list
        return all(scope in key_scopes for scope in scopes)
    
    def is_valid(self) -> bool:
        """Check if the API key is valid and can be used"""
        if not self.is_active or self.revoked:
            return False
        
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
            
        return True
    
    def update_usage(self):
        """Update last used timestamp and usage count"""
        self.last_used_at = datetime.utcnow()
        self.usage_count += 1
    
    @classmethod
    def generate_key(cls) -> tuple[str, str]:
        """Generate a new API key and return (raw_key, prefix)"""
        # Generate secure random key
        raw_key = f"et_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:11]  # et_xxxxxxxx format
        return raw_key, prefix
    
    @classmethod
    def hash_key(cls, raw_key: str) -> str:
        """Hash an API key using bcrypt"""
        return bcrypt.hashpw(raw_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_key(self, raw_key: str) -> bool:
        """Verify a raw API key against the stored hash"""
        try:
            return bcrypt.checkpw(raw_key.encode('utf-8'), self.hashed_key.encode('utf-8'))
        except Exception:
            return False
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_api_key_user_id', 'user_id'),
        Index('idx_api_key_prefix', 'prefix'),
        Index('idx_api_key_active', 'is_active'),
        Index('idx_api_key_revoked', 'revoked'),
        Index('idx_api_key_expires_at', 'expires_at'),
        Index('idx_api_key_last_used', 'last_used_at'),
        Index('idx_api_key_created_at', 'created_at'),
    )


class ApiKeyUsage(Base):
    """API Key usage tracking and analytics"""
    __tablename__ = "api_key_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=False)
    
    # Request information
    endpoint = Column(String, nullable=False)  # '/api/v1/emails/send'
    method = Column(String, nullable=False)    # 'POST', 'GET', etc.
    status_code = Column(Integer, nullable=False)  # HTTP response status
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    
    # Client information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)  # Request correlation ID
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Error information (if any)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Request size (optional)
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # Relationships
    api_key = relationship("ApiKey", back_populates="usage_records")
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_usage_api_key_id', 'api_key_id'),
        Index('idx_usage_timestamp', 'timestamp'),
        Index('idx_usage_endpoint', 'endpoint'),
        Index('idx_usage_status_code', 'status_code'),
        Index('idx_usage_api_key_timestamp', 'api_key_id', 'timestamp'),
        Index('idx_usage_ip_address', 'ip_address'),
    )


# ============================================
# API Key Scopes and Presets
# ============================================

# Predefined scopes for API keys
API_KEY_SCOPES = {
    # Email operations
    'emails:send': 'Send emails',
    'emails:read': 'Read email tracking data',
    'emails:bulk': 'Send bulk emails',
    
    # Campaign operations
    'campaigns:create': 'Create campaigns',
    'campaigns:read': 'Read campaigns',
    'campaigns:update': 'Update campaigns',
    'campaigns:delete': 'Delete campaigns',
    
    # Contact operations
    'contacts:create': 'Create contacts',
    'contacts:read': 'Read contacts',
    'contacts:update': 'Update contacts',
    'contacts:delete': 'Delete contacts',
    'contacts:import': 'Import contacts',
    'contacts:export': 'Export contacts',
    
    # Analytics operations
    'analytics:read': 'Read analytics data',
    'analytics:export': 'Export analytics',
    
    # Template operations
    'templates:create': 'Create templates',
    'templates:read': 'Read templates',
    'templates:update': 'Update templates',
    'templates:delete': 'Delete templates',
    
    # Webhook operations
    'webhooks:create': 'Create webhooks',
    'webhooks:read': 'Read webhooks',
    'webhooks:update': 'Update webhooks',
    'webhooks:delete': 'Delete webhooks',
    
    # Full access
    '*': 'Full access to all resources'
}

# Common scope combinations
SCOPE_PRESETS = {
    'full_access': ['*'],
    'email_only': ['emails:send', 'emails:read', 'emails:bulk'],
    'readonly': ['emails:read', 'campaigns:read', 'contacts:read', 'analytics:read', 'templates:read'],
    'campaign_management': ['campaigns:create', 'campaigns:read', 'campaigns:update', 'campaigns:delete', 'emails:send', 'emails:read'],
    'contact_management': ['contacts:create', 'contacts:read', 'contacts:update', 'contacts:delete', 'contacts:import', 'contacts:export'],
}
