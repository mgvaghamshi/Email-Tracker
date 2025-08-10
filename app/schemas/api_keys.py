"""
Pydantic schemas for API key management
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


class ApiKeyCreate(BaseModel):
    """Schema for creating a new API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the API key")
    scopes: List[str] = Field(default=["*"], description="List of scopes for the API key")
    requests_per_minute: Optional[int] = Field(default=100, ge=1, le=10000, description="Rate limit per minute")
    requests_per_day: Optional[int] = Field(default=10000, ge=1, le=1000000, description="Rate limit per day")
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=3650, description="Expiration in days (optional)")
    
    @validator('scopes')
    def validate_scopes(cls, v):
        if not v:
            return ["*"]
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Production API Key",
                "scopes": ["emails:send", "emails:read", "campaigns:read"],
                "requests_per_minute": 100,
                "requests_per_day": 10000,
                "expires_in_days": 365
            }
        }


class ApiKeyUpdate(BaseModel):
    """Schema for updating an existing API key"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    scopes: Optional[List[str]] = Field(None)
    is_active: Optional[bool] = Field(None)
    requests_per_minute: Optional[int] = Field(None, ge=1, le=10000)
    requests_per_day: Optional[int] = Field(None, ge=1, le=1000000)
    expires_in_days: Optional[int] = Field(None, ge=0, le=3650)  # 0 means remove expiration
    
    class Config:
        json_schema_extra = {
            "example": {
                "name": "Updated Production Key",
                "scopes": ["emails:send", "campaigns:read"],
                "is_active": True,
                "requests_per_minute": 150
            }
        }


class ApiKeyResponse(BaseModel):
    """Schema for API key response"""
    id: str
    name: str
    key: Optional[str] = Field(None, description="Raw API key (only returned during creation)")
    prefix: str = Field(..., description="Key prefix for identification")
    scopes: List[str]
    requests_per_minute: int
    requests_per_day: int
    is_active: bool
    revoked: bool = False
    revoked_at: Optional[datetime] = None
    revoked_reason: Optional[str] = None
    usage_count: int = 0
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "api_key_123",
                "name": "Production API Key",
                "key": "et_AbCdEf123456...",  # Only shown during creation
                "prefix": "et_AbCdEf12",
                "scopes": ["emails:send", "emails:read"],
                "requests_per_minute": 100,
                "requests_per_day": 10000,
                "is_active": True,
                "revoked": False,
                "usage_count": 1250,
                "last_used_at": "2025-07-30T10:30:00Z",
                "expires_at": "2026-07-30T10:30:00Z",
                "created_at": "2025-01-30T10:30:00Z"
            }
        }


class ApiKeyListResponse(BaseModel):
    """Schema for listing API keys"""
    keys: List[ApiKeyResponse]
    total: int
    skip: int
    limit: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "keys": [
                    {
                        "id": "api_key_123",
                        "name": "Production Key",
                        "prefix": "et_AbCdEf12",
                        "scopes": ["*"],
                        "is_active": True,
                        "usage_count": 1250
                    }
                ],
                "total": 3,
                "skip": 0,
                "limit": 50
            }
        }


class ApiKeyUsageResponse(BaseModel):
    """Schema for API key usage log entry"""
    id: str
    endpoint: str
    method: str
    status_code: int
    request_time: datetime
    response_time_ms: Optional[int] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    error_message: Optional[str] = None
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "usage_123",
                "endpoint": "/api/v1/emails/send",
                "method": "POST",
                "status_code": 202,
                "request_time": "2025-07-30T10:30:00Z",
                "response_time_ms": 150,
                "ip_address": "192.168.1.100",
                "user_agent": "MyApp/1.0"
            }
        }


class ApiKeyStatsResponse(BaseModel):
    """Schema for API key usage statistics"""
    total_requests: int
    successful_requests: int
    success_rate: float = Field(..., description="Success rate as percentage")
    period_days: int
    top_endpoints: List[Dict[str, Any]]
    last_used_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_requests": 10500,
                "successful_requests": 10234,
                "success_rate": 97.46,
                "period_days": 30,
                "top_endpoints": [
                    {"endpoint": "/api/v1/emails/send", "count": 8500},
                    {"endpoint": "/api/v1/campaigns", "count": 1200},
                    {"endpoint": "/api/v1/analytics/dashboard", "count": 800}
                ],
                "last_used_at": "2025-07-30T10:30:00Z"
            }
        }


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "API key has been revoked successfully"
            }
        }


# Scope validation schema
class ScopeInfo(BaseModel):
    """Information about an API key scope"""
    scope: str
    description: str
    category: str


class AvailableScopesResponse(BaseModel):
    """Response for available scopes endpoint"""
    scopes: Dict[str, str]
    presets: Dict[str, List[str]]
    categories: List[str] = ["emails", "campaigns", "contacts", "analytics", "templates", "webhooks", "admin"]
    
    class Config:
        json_schema_extra = {
            "example": {
                "scopes": {
                    "emails:send": "Send emails",
                    "emails:read": "Read email tracking data",
                    "campaigns:read": "Read campaigns",
                    "*": "Full access"
                },
                "presets": {
                    "full_access": ["*"],
                    "email_only": ["emails:send", "emails:read"],
                    "readonly": ["emails:read", "campaigns:read", "analytics:read"]
                }
            }
        }
