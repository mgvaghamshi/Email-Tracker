"""
User authentication and management models
"""
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

# Import Base from models.py to use the same declarative base
from ..models import Base


class UserStatus(str, enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class User(Base):
    """User account model"""
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=True, index=True)
    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    
    # Account status
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False)
    
    # Security
    failed_login_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime, nullable=True)
    require_password_change = Column(Boolean, default=False, nullable=False)
    
    # 2FA
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    two_factor_secret = Column(String, nullable=True)
    
    # Email verification
    email_verification_token = Column(String, nullable=True)
    email_verification_sent_at = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)
    
    # Password reset
    password_reset_token = Column(String, nullable=True)
    password_reset_sent_at = Column(DateTime, nullable=True)
    password_reset_expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    login_attempts = relationship("LoginAttempt", back_populates="user", cascade="all, delete-orphan")
    user_roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    
    def is_locked(self) -> bool:
        """Check if account is currently locked"""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    def lock_account(self, duration_minutes: int = 30):
        """Lock the account for specified duration"""
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
    
    def unlock_account(self):
        """Unlock the account"""
        self.locked_until = None
        self.failed_login_attempts = 0


class UserSession(Base):
    """User session model for tracking active sessions"""
    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Session details
    refresh_token = Column(String, unique=True, nullable=False, index=True)
    access_token_jti = Column(String, nullable=True)  # JWT ID for access token
    
    # Device/Location info
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)
    device_name = Column(String, nullable=True)
    device_type = Column(String, nullable=True)  # web, mobile, desktop
    browser = Column(String, nullable=True)
    os = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    # Session status
    is_active = Column(Boolean, default=True, nullable=False)
    is_current = Column(Boolean, default=False, nullable=False)  # Current active session
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_activity_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """Check if session is valid (active and not expired)"""
        return self.is_active and not self.is_expired() and self.revoked_at is None


class LoginAttempt(Base):
    """Login attempt tracking for security monitoring"""
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    email = Column(String, nullable=False, index=True)
    
    # Attempt details
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String, nullable=True)
    
    # Device/Location info
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    device_type = Column(String, nullable=True)
    browser = Column(String, nullable=True)
    os = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    # Security flags
    is_suspicious = Column(Boolean, default=False, nullable=False)
    requires_verification = Column(Boolean, default=False, nullable=False)
    
    # Timestamp
    attempted_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    user = relationship("User", back_populates="login_attempts")


class Role(Base):
    """Role model for RBAC"""
    __tablename__ = "roles"

    id = Column(String, primary_key=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Role properties
    is_system = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted
    is_default = Column(Boolean, default=False, nullable=False)  # Assigned to new users
    
    # Permissions (JSON or comma-separated)
    permissions = Column(Text, nullable=True)  # Store as JSON string
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class UserRole(Base):
    """User-Role association model"""
    __tablename__ = "user_roles"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_id = Column(String, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Optional expiration
    expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    assigned_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")
    
    def is_expired(self) -> bool:
        """Check if role assignment is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
