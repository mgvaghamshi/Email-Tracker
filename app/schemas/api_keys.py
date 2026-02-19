"""
API Key schemas for programmatic authentication
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ApiKeyCreateRequest(BaseModel):
    """Request schema for creating an API key"""
    name: str = Field(..., description="Friendly name for the API key")
    requests_per_minute: int = Field(default=100, ge=1, le=10000)
    requests_per_day: int = Field(default=10000, ge=1, le=1000000)
    expires_in_days: Optional[int] = Field(None, ge=1, le=3650, description="Days until expiration (max 10 years)")


class ApiKeyResponse(BaseModel):
    """Response schema for API key (without actual key)"""
    id: str
    name: str
    key_prefix: str  # First 8 chars like "et_12345678"
    requests_per_minute: int
    requests_per_day: int
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    last_used_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    """Response schema when creating API key (includes actual key once)"""
    api_key: str  # Full API key - only shown once!


class ApiKeyUpdateRequest(BaseModel):
    """Request schema for updating an API key"""
    name: Optional[str] = None
    requests_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    requests_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    is_active: Optional[bool] = None


class ApiKeyUsageStats(BaseModel):
    """API key usage statistics"""
    api_key_id: str
    api_key_name: str
    current_minute_requests: int
    current_day_requests: int
    requests_per_minute_limit: int
    requests_per_day_limit: int
    remaining_minute_requests: int
    remaining_day_requests: int


class ApiKeyListResponse(BaseModel):
    """Response schema for listing API keys"""
    api_keys: list[ApiKeyResponse]
    total: int
