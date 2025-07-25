"""
Authentication-related Pydantic schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class ApiKeyCreateRequest(BaseModel):
    """Request schema for creating an API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the API key")
    user_id: Optional[str] = Field(None, description="Optional user ID to associate with this key")
    requests_per_minute: int = Field(100, ge=1, le=10000, description="Rate limit: requests per minute")
    requests_per_day: int = Field(10000, ge=1, le=1000000, description="Rate limit: requests per day")
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="Key expiration in days (optional)")
    
    @validator('requests_per_day')
    def validate_daily_limit(cls, v, values):
        if 'requests_per_minute' in values:
            # Daily limit should be reasonable compared to per-minute limit
            max_theoretical_daily = values['requests_per_minute'] * 60 * 24
            if v > max_theoretical_daily:
                v = max_theoretical_daily
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Production API Key",
                "user_id": "user_123",
                "requests_per_minute": 100,
                "requests_per_day": 10000,
                "expires_in_days": 365
            }
        }


class ApiKeyResponse(BaseModel):
    """Response schema for API key information"""
    id: str = Field(..., description="API key ID")
    key: Optional[str] = Field(None, description="API key (only shown once during creation)")
    name: str = Field(..., description="Friendly name")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    is_active: bool = Field(..., description="Whether the key is active")
    created_at: datetime = Field(..., description="When the key was created")
    last_used_at: Optional[datetime] = Field(None, description="When the key was last used")
    expires_at: Optional[datetime] = Field(None, description="When the key expires")
    requests_per_minute: int = Field(..., description="Rate limit: requests per minute")
    requests_per_day: int = Field(..., description="Rate limit: requests per day")
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "ak_550e8400-e29b-41d4-a716-446655440000",
                "key": "et_abc123def456...",
                "name": "Production API Key",
                "user_id": "user_123",
                "is_active": True,
                "created_at": "2025-01-25T10:00:00Z",
                "last_used_at": "2025-01-25T15:30:00Z",
                "expires_at": "2026-01-25T10:00:00Z",
                "requests_per_minute": 100,
                "requests_per_day": 10000
            }
        }


class ApiKeyListResponse(BaseModel):
    """Response schema for listing API keys"""
    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="Friendly name")
    user_id: Optional[str] = Field(None, description="Associated user ID")
    is_active: bool = Field(..., description="Whether the key is active")
    created_at: datetime = Field(..., description="When the key was created")
    last_used_at: Optional[datetime] = Field(None, description="When the key was last used")
    expires_at: Optional[datetime] = Field(None, description="When the key expires")
    requests_per_minute: int = Field(..., description="Rate limit: requests per minute")
    requests_per_day: int = Field(..., description="Rate limit: requests per day")
    
    class Config:
        from_attributes = True


class ApiKeyUpdateRequest(BaseModel):
    """Request schema for updating an API key"""
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New friendly name")
    is_active: Optional[bool] = Field(None, description="Whether to activate/deactivate the key")
    requests_per_minute: Optional[int] = Field(None, ge=1, le=10000, description="New rate limit: requests per minute")
    requests_per_day: Optional[int] = Field(None, ge=1, le=1000000, description="New rate limit: requests per day")
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Updated API Key Name",
                "is_active": True,
                "requests_per_minute": 200,
                "requests_per_day": 20000
            }
        }


class ApiKeyUsageStats(BaseModel):
    """Response schema for API key usage statistics"""
    api_key_id: str = Field(..., description="API key ID")
    current_minute_requests: int = Field(..., description="Requests in current minute")
    current_day_requests: int = Field(..., description="Requests in current day")
    limit_minute: int = Field(..., description="Per-minute limit")
    limit_day: int = Field(..., description="Per-day limit")
    remaining_minute: int = Field(..., description="Remaining requests this minute")
    remaining_day: int = Field(..., description="Remaining requests today")
    
    class Config:
        schema_extra = {
            "example": {
                "api_key_id": "ak_550e8400-e29b-41d4-a716-446655440000",
                "current_minute_requests": 15,
                "current_day_requests": 2450,
                "limit_minute": 100,
                "limit_day": 10000,
                "remaining_minute": 85,
                "remaining_day": 7550
            }
        }
