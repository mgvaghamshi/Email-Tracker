"""
User authentication and management schemas
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


# ============= Authentication Schemas =============

class UserCreate(BaseModel):
    """Schema for user registration"""
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = None
    username: Optional[str] = None


class LoginRequest(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    remember_me: Optional[bool] = False


class LoginResponse(BaseModel):
    """Schema for login response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============= User Management Schemas =============

class UserResponse(BaseModel):
    """Schema for user information"""
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool
    two_factor_enabled: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: Optional[str] = None
    username: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    """Schema for password change"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @validator('new_password')
    def passwords_different(cls, v, values):
        if 'current_password' in values and v == values['current_password']:
            raise ValueError('New password must be different from current password')
        return v


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)


class EmailVerificationRequest(BaseModel):
    """Schema for email verification request"""
    email: EmailStr


class EmailVerificationConfirm(BaseModel):
    """Schema for email verification confirmation"""
    token: str


# ============= Session Management Schemas =============

class SessionResponse(BaseModel):
    """Schema for user session"""
    id: str
    device_name: Optional[str]
    device_type: Optional[str]
    browser: Optional[str]
    os: Optional[str]
    ip_address: Optional[str]
    location: Optional[str]
    is_current: bool
    created_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schema for session list"""
    sessions: List[SessionResponse]
    total: int


# ============= Admin Schemas =============

class UserAdminUpdate(BaseModel):
    """Schema for admin user updates"""
    full_name: Optional[str] = None
    username: Optional[str] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None
    is_superuser: Optional[bool] = None


class UserWithRolesResponse(BaseModel):
    """Schema for user with roles"""
    id: str
    email: str
    username: Optional[str]
    full_name: Optional[str]
    is_active: bool
    is_verified: bool
    is_superuser: bool
    two_factor_enabled: bool
    created_at: datetime
    last_login_at: Optional[datetime]
    roles: List["RoleResponse"]
    
    class Config:
        from_attributes = True


class RoleResponse(BaseModel):
    """Schema for role"""
    id: str
    name: str
    description: Optional[str]
    is_system: bool
    permissions: Optional[str]
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Schema for user list"""
    users: List[UserWithRolesResponse]
    total: int
    page: int
    per_page: int


# ============= Statistics Schemas =============

class UserStats(BaseModel):
    """User statistics"""
    total_users: int
    active_users: int
    inactive_users: int
    unverified_users: int
    new_users_30d: int


class SecurityStats(BaseModel):
    """Security statistics"""
    locked_accounts: int
    failed_logins_24h: int
    suspicious_activities: int
    two_factor_enabled: int


# ============= Generic Response Schemas =============

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    success: bool = True


# Update forward references
LoginResponse.model_rebuild()
UserWithRolesResponse.model_rebuild()
