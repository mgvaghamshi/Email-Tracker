"""
User management Pydantic schemas
"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


# ============================================================================
# Base User Schemas
# ============================================================================

class UserBase(BaseModel):
    """Base user schema with common fields"""
    email: EmailStr = Field(..., description="User's email address")
    first_name: Optional[str] = Field(None, min_length=1, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, min_length=1, max_length=50, description="Last name")
    timezone: Optional[str] = Field("UTC", description="User's timezone")
    locale: Optional[str] = Field("en", description="User's locale preference")


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=128, description="User's password")
    password_confirm: str = Field(..., description="Password confirmation")
    
    @validator('password')
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
    
    @validator('password_confirm')
    def validate_passwords_match(cls, v, values):
        """Ensure password and confirmation match"""
        if 'password' in values and v != values['password']:
            raise ValueError("Passwords do not match")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "timezone": "UTC",
                "locale": "en"
            }
        }


class UserResponse(UserBase):
    """Schema for user response (public info)"""
    id: str = Field(..., description="User ID")
    full_name: Optional[str] = Field(None, description="Full name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    is_active: bool = Field(..., description="Account is active")
    is_verified: bool = Field(..., description="Email is verified")
    created_at: datetime = Field(..., description="Account creation timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "usr_550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "full_name": "John Doe",
                "avatar_url": "https://example.com/avatar.jpg",
                "is_active": True,
                "is_verified": True,
                "created_at": "2025-01-25T10:00:00Z",
                "last_login_at": "2025-01-25T15:30:00Z",
                "timezone": "UTC",
                "locale": "en"
            }
        }


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=50)
    last_name: Optional[str] = Field(None, min_length=1, max_length=50)
    avatar_url: Optional[str] = Field(None)
    timezone: Optional[str] = Field(None)
    locale: Optional[str] = Field(None)
    preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences JSON")
    
    class Config:
        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "timezone": "America/New_York",
                "locale": "en-US",
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            }
        }


# ============================================================================
# Authentication Schemas
# ============================================================================

class LoginRequest(BaseModel):
    """Schema for user login"""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")
    remember_me: bool = Field(False, description="Extend session duration")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com",
                "password": "SecurePass123!",
                "remember_me": False,
                "device_info": {
                    "device_type": "desktop",
                    "browser": "Chrome",
                    "os": "Windows"
                }
            }
        }


class LoginResponse(BaseModel):
    """Schema for login response"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    user: UserResponse = Field(..., description="User information")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "user": {
                    "id": "usr_550e8400-e29b-41d4-a716-446655440000",
                    "email": "john.doe@example.com",
                    "first_name": "John",
                    "last_name": "Doe"
                }
            }
        }


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request"""
    refresh_token: str = Field(..., description="Refresh token")
    
    class Config:
        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response"""
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }


# ============================================================================
# Password Management Schemas
# ============================================================================

class PasswordChangeRequest(BaseModel):
    """Schema for password change request"""
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    new_password_confirm: str = Field(..., description="New password confirmation")
    
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
    def validate_passwords_match(cls, v, values):
        """Ensure password and confirmation match"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Passwords do not match")
        return v


class PasswordResetRequest(BaseModel):
    """Schema for password reset request"""
    email: EmailStr = Field(..., description="User's email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "john.doe@example.com"
            }
        }


class PasswordResetConfirm(BaseModel):
    """Schema for password reset confirmation"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password")
    new_password_confirm: str = Field(..., description="New password confirmation")
    
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
    def validate_passwords_match(cls, v, values):
        """Ensure password and confirmation match"""
        if 'new_password' in values and v != values['new_password']:
            raise ValueError("Passwords do not match")
        return v


# ============================================================================
# Session Management Schemas
# ============================================================================

class SessionResponse(BaseModel):
    """Schema for user session information"""
    id: str = Field(..., description="Session ID")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    ip_address: Optional[str] = Field(None, description="IP address")
    location: Optional[str] = Field(None, description="Geographic location")
    is_current: bool = Field(..., description="Is this the current session")
    created_at: datetime = Field(..., description="Session creation time")
    last_activity: datetime = Field(..., description="Last activity time")
    expires_at: datetime = Field(..., description="Session expiration time")
    
    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Schema for listing user sessions"""
    sessions: List[SessionResponse] = Field(..., description="List of active sessions")
    current_session_id: str = Field(..., description="Current session ID")
    
    class Config:
        json_schema_extra = {
            "example": {
                "sessions": [
                    {
                        "id": "sess_550e8400-e29b-41d4-a716-446655440000",
                        "device_info": {"device_type": "desktop", "browser": "Chrome"},
                        "ip_address": "192.168.1.100",
                        "location": "New York, US",
                        "is_current": True,
                        "created_at": "2025-01-25T10:00:00Z",
                        "last_activity": "2025-01-25T15:30:00Z",
                        "expires_at": "2025-02-25T10:00:00Z"
                    }
                ],
                "current_session_id": "sess_550e8400-e29b-41d4-a716-446655440000"
            }
        }


# ============================================================================
# Email Verification Schemas
# ============================================================================

class EmailVerificationRequest(BaseModel):
    """Schema for requesting email verification"""
    email: Optional[EmailStr] = Field(None, description="Email to verify (current user's email if not provided)")


class EmailVerificationConfirm(BaseModel):
    """Schema for confirming email verification"""
    token: str = Field(..., description="Email verification token")


# ============================================================================
# Role and Permission Schemas
# ============================================================================

class RoleResponse(BaseModel):
    """Schema for role information"""
    id: str = Field(..., description="Role ID")
    name: str = Field(..., description="Role name")
    display_name: str = Field(..., description="Role display name")
    description: Optional[str] = Field(None, description="Role description")
    permissions: List[str] = Field(..., description="List of permissions")
    is_system: bool = Field(..., description="Is system role")
    
    class Config:
        from_attributes = True


class UserWithRolesResponse(UserResponse):
    """Schema for user with roles information"""
    roles: List[RoleResponse] = Field(..., description="User's roles")
    permissions: List[str] = Field(..., description="All user permissions")


# ============================================================================
# Admin Schemas
# ============================================================================

class UserListFilter(BaseModel):
    """Schema for filtering user list"""
    email: Optional[str] = Field(None, description="Filter by email (partial match)")
    is_active: Optional[bool] = Field(None, description="Filter by active status")
    is_verified: Optional[bool] = Field(None, description="Filter by verification status")
    created_after: Optional[datetime] = Field(None, description="Filter users created after date")
    created_before: Optional[datetime] = Field(None, description="Filter users created before date")
    role_name: Optional[str] = Field(None, description="Filter by role name")
    page: int = Field(1, ge=1, description="Page number")
    size: int = Field(20, ge=1, le=100, description="Page size")


class UserListResponse(BaseModel):
    """Schema for paginated user list"""
    users: List[UserWithRolesResponse] = Field(..., description="List of users")
    total: int = Field(..., description="Total number of users")
    page: int = Field(..., description="Current page")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")


class UserAdminUpdate(UserUpdate):
    """Schema for admin user updates"""
    is_active: Optional[bool] = Field(None, description="Account active status")
    is_verified: Optional[bool] = Field(None, description="Email verification status")
    is_superuser: Optional[bool] = Field(None, description="Superuser status")


# ============================================================================
# Generic Response Schemas
# ============================================================================

class MessageResponse(BaseModel):
    """Generic message response"""
    message: str = Field(..., description="Response message")
    detail: Optional[str] = Field(None, description="Additional details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Operation completed successfully",
                "detail": "Additional information about the operation"
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response"""
    success: bool = Field(True, description="Operation success status")
    message: str = Field(..., description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Additional data")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {}
            }
        }
