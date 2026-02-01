"""
Security-related Pydantic schemas for EmailTracker API
"""
from pydantic import BaseModel, validator, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
import re


# ============================================================================
# Password Management Schemas
# ============================================================================

class PasswordChangeRequest(BaseModel):
    """Request schema for password change"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: Optional[str] = Field(None, description="New password confirmation")
    new_password_confirm: Optional[str] = Field(None, description="New password confirmation (alternative field name)")
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password meets security requirements"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
    
    @validator('new_password_confirm')
    def passwords_match(cls, v, values):
        new_password = values.get('new_password')
        confirm_password = values.get('confirm_password')
        
        # Use either field for confirmation
        confirmation = v or confirm_password
        
        if not confirmation:
            raise ValueError('Password confirmation is required')
        
        if new_password and confirmation != new_password:
            raise ValueError('Passwords do not match')
        return v
    
    @validator('confirm_password')
    def confirm_password_validation(cls, v, values):
        if v and 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class PasswordStrengthRequest(BaseModel):
    """Request schema for password strength check"""
    password: str = Field(..., description="Password to check strength for")


class PasswordStrengthResponse(BaseModel):
    """Response schema for password strength analysis"""
    is_strong: bool
    strength: str  # "Weak", "Medium", "Strong"
    score: int
    max_score: int
    issues: List[str]


class PasswordChangeResponse(BaseModel):
    """Response schema for password change"""
    success: bool
    message: str
    password_strength: PasswordStrengthResponse


# ============================================================================
# Security Settings Schemas
# ============================================================================

class SecuritySettingsResponse(BaseModel):
    """Response schema for security settings"""
    # Two-factor authentication
    two_factor_enabled: bool
    two_factor_verified: bool
    backup_codes_remaining: int
    
    # Password information
    password_changed_at: Optional[datetime]
    password_age_days: Optional[int]
    
    # Session information
    active_sessions_count: int
    recent_login_attempts: int
    
    # Settings
    session_timeout_hours: int
    max_concurrent_sessions: int
    login_notifications: bool
    suspicious_activity_alerts: bool
    
    # API key settings
    api_key_rotation_enabled: bool
    api_key_rotation_days: int
    
    # Password policy
    require_password_change: bool
    password_change_days: int


class SecuritySettingsUpdateRequest(BaseModel):
    """Request schema for updating security settings"""
    session_timeout_hours: Optional[int] = Field(None, ge=1, le=168)  # 1 hour to 1 week
    max_concurrent_sessions: Optional[int] = Field(None, ge=1, le=20)
    login_notifications: Optional[bool] = None
    suspicious_activity_alerts: Optional[bool] = None
    api_key_rotation_enabled: Optional[bool] = None
    api_key_rotation_days: Optional[int] = Field(None, ge=7, le=365)  # 1 week to 1 year
    require_password_change: Optional[bool] = None
    password_change_days: Optional[int] = Field(None, ge=1, le=365)  # 1 day to 1 year


# ============================================================================
# Session Management Schemas
# ============================================================================

class SessionResponse(BaseModel):
    """Response schema for user session"""
    id: str
    device_name: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    location: Optional[str]
    created_at: datetime
    last_activity: datetime
    last_activity_relative: Optional[str] = Field(None, description="Human-readable relative time")
    expires_at: datetime
    is_current: bool


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogResponse(BaseModel):
    """Response schema for security audit log entry"""
    id: str
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    description: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    success: bool
    failure_reason: Optional[str]
    security_metadata: Optional[Dict[str, Any]]  # Changed from 'metadata'
    timestamp: datetime
    timestamp_relative: Optional[str] = Field(None, description="Human-readable relative time")


# ============================================================================
# Security Statistics Schemas
# ============================================================================

class SecurityStatsResponse(BaseModel):
    """Response schema for security statistics"""
    total_login_attempts: int
    successful_logins: int
    failed_logins: int
    unique_ip_addresses: int
    security_events: int
    two_factor_enabled: bool
    two_factor_last_used: Optional[datetime]
    period_days: int


# ============================================================================
# Login and Authentication Schemas
# ============================================================================

class LoginAttemptResponse(BaseModel):
    """Response schema for login attempt"""
    id: str
    email: str
    success: bool
    failure_reason: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    attempted_at: datetime
    requires_2fa: bool
    two_factor_completed: bool


# ============================================================================
# Password Reset Schemas
# ============================================================================

class PasswordResetRequestSchema(BaseModel):
    """Request schema for password reset"""
    email: str = Field(..., description="Email address")
    
    @validator('email')
    def validate_email(cls, v):
        # Basic email validation
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
            raise ValueError('Invalid email format')
        return v.lower()


class PasswordResetConfirmSchema(BaseModel):
    """Schema for password reset confirmation"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    confirm_password: str = Field(..., description="New password confirmation")
    
    @validator('new_password')
    def validate_password_strength(cls, v):
        """Validate password meets security requirements"""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


# ============================================================================
# Device and Location Schemas
# ============================================================================

class DeviceInfoSchema(BaseModel):
    """Schema for device information"""
    device_name: str
    device_type: str  # "desktop", "mobile", "tablet"
    browser: Optional[str]
    os: Optional[str]
    is_trusted: bool = False


class LocationInfoSchema(BaseModel):
    """Schema for location information"""
    ip_address: str
    country: Optional[str]
    region: Optional[str]
    city: Optional[str]
    is_known_location: bool = False
