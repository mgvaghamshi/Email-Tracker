"""
Two-Factor Authentication schemas for EmailTracker API
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class TwoFactorSetupRequest(BaseModel):
    """Request to initiate 2FA setup"""
    pass


class TwoFactorSetupResponse(BaseModel):
    """Response with 2FA setup details"""
    secret: str = Field(..., description="Base32 encoded TOTP secret")
    qr_code_url: str = Field(..., description="URL to QR code image")
    backup_codes: List[str] = Field(..., description="One-time backup codes")
    setup_uri: str = Field(..., description="TOTP provisioning URI")
    
    class Config:
        json_schema_extra = {
            "example": {
                "secret": "JBSWY3DPEHPK3PXP",
                "qr_code_url": "/api/v1/auth/2fa/qr",
                "backup_codes": ["12345678", "87654321", "11223344"],
                "setup_uri": "otpauth://totp/EmailTracker:user@example.com?secret=JBSWY3DPEHPK3PXP&issuer=EmailTracker"
            }
        }


class TwoFactorVerifyRequest(BaseModel):
    """Request to verify 2FA setup"""
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "123456"
            }
        }


class TwoFactorVerifyResponse(BaseModel):
    """Response after 2FA verification"""
    success: bool = Field(..., description="Whether verification was successful")
    message: str = Field(..., description="Success or error message")
    backup_codes_remaining: Optional[int] = Field(None, description="Number of backup codes remaining")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Two-factor authentication enabled successfully",
                "backup_codes_remaining": 8
            }
        }


class TwoFactorLoginRequest(BaseModel):
    """Request for 2FA during login"""
    code: str = Field(..., min_length=6, max_length=8, description="6-digit TOTP code or 8-digit backup code")
    session_token: str = Field(..., description="Temporary session token from initial login")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "123456",
                "session_token": "temp_session_token_here"
            }
        }


class TwoFactorLoginResponse(BaseModel):
    """Response after successful 2FA login"""
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    backup_codes_remaining: Optional[int] = Field(None, description="Number of backup codes remaining")
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600,
                "backup_codes_remaining": 7
            }
        }


class TwoFactorDisableRequest(BaseModel):
    """Request to disable 2FA"""
    password: str = Field(..., description="Current password for verification")
    code: Optional[str] = Field(None, min_length=6, max_length=8, description="2FA code or backup code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "password": "current_password",
                "code": "123456"
            }
        }


class TwoFactorStatusResponse(BaseModel):
    """Current 2FA status for user"""
    is_enabled: bool = Field(..., description="Whether 2FA is enabled")
    is_verified: bool = Field(..., description="Whether 2FA setup is verified")
    backup_codes_remaining: int = Field(..., description="Number of backup codes remaining")
    setup_completed_at: Optional[datetime] = Field(None, description="When 2FA setup was completed")
    last_used_at: Optional[datetime] = Field(None, description="When 2FA was last used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "is_enabled": True,
                "is_verified": True,
                "backup_codes_remaining": 6,
                "setup_completed_at": "2024-01-15T10:30:00Z",
                "last_used_at": "2024-01-20T09:15:00Z"
            }
        }


class TwoFactorBackupCodesResponse(BaseModel):
    """Response with new backup codes"""
    backup_codes: List[str] = Field(..., description="New backup codes")
    message: str = Field(..., description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "backup_codes": ["12345678", "87654321", "11223344", "44332211", "55667788"],
                "message": "New backup codes generated successfully"
            }
        }


class TwoFactorRecoveryRequest(BaseModel):
    """Request for 2FA account recovery"""
    email: str = Field(..., description="User email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class TwoFactorRecoveryResponse(BaseModel):
    """Response for 2FA recovery request"""
    message: str = Field(..., description="Recovery instructions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Recovery instructions have been sent to your email address"
            }
        }


class TwoFactorQRCodeResponse(BaseModel):
    """Response for QR code image"""
    qr_code_data: str = Field(..., description="Base64 encoded QR code image")
    content_type: str = Field(default="image/png", description="Image content type")
    
    class Config:
        json_schema_extra = {
            "example": {
                "qr_code_data": "iVBORw0KGgoAAAANSUhEUgAAAQgAAAEI...",
                "content_type": "image/png"
            }
        }


# Updated Security Settings schemas to include 2FA details
class SecuritySettings(BaseModel):
    """Enhanced security settings with 2FA details"""
    twoFactorEnabled: bool = Field(False, description="Whether 2FA is enabled")
    twoFactorVerified: bool = Field(False, description="Whether 2FA setup is verified")
    backupCodesRemaining: int = Field(0, description="Number of backup codes remaining")
    apiKeyRotationEnabled: bool = Field(False, description="Whether API key rotation is enabled")
    sessionTimeout: int = Field(30, description="Session timeout in minutes")
    lastTwoFactorUsed: Optional[datetime] = Field(None, description="When 2FA was last used")
    
    class Config:
        json_schema_extra = {
            "example": {
                "twoFactorEnabled": True,
                "twoFactorVerified": True,
                "backupCodesRemaining": 6,
                "apiKeyRotationEnabled": False,
                "sessionTimeout": 30,
                "lastTwoFactorUsed": "2024-01-20T09:15:00Z"
            }
        }


class SecuritySettingsResponse(SecuritySettings):
    """Response model for security settings"""
    pass


class TwoFactorSessionResponse(BaseModel):
    """Response for 2FA session creation"""
    session_token: str = Field(..., description="Temporary session token")
    expires_in: int = Field(..., description="Session expiration in seconds")
    requires_2fa: bool = Field(True, description="Whether 2FA is required")
    
    class Config:
        json_schema_extra = {
            "example": {
                "session_token": "temp_session_token_here",
                "expires_in": 300,
                "requires_2fa": True
            }
        }
