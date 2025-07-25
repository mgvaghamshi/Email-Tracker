"""
Tracking-related Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class EmailEventResponse(BaseModel):
    """Response schema for email events"""
    id: str = Field(..., description="Event ID")
    tracker_id: str = Field(..., description="Associated tracker ID")
    event_type: str = Field(..., description="Type of event: open, click, bounce, complaint")
    timestamp: datetime = Field(..., description="When the event occurred")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    country: Optional[str] = Field(None, description="Country from IP geolocation")
    city: Optional[str] = Field(None, description="City from IP geolocation")
    device_type: Optional[str] = Field(None, description="Device type: desktop, mobile, tablet")
    client_name: Optional[str] = Field(None, description="Email client name")
    client_version: Optional[str] = Field(None, description="Email client version")
    is_bot: bool = Field(..., description="Whether this event was flagged as a bot")
    bot_reason: Optional[str] = Field(None, description="Reason for bot detection")
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "event_550e8400-e29b-41d4-a716-446655440000",
                "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
                "event_type": "open",
                "timestamp": "2025-01-25T10:05:00Z",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ip_address": "192.168.1.1",
                "country": "United States",
                "city": "New York",
                "device_type": "desktop",
                "client_name": "Gmail",
                "client_version": "2025.01.25",
                "is_bot": False,
                "bot_reason": None
            }
        }


class EmailClickResponse(BaseModel):
    """Response schema for email clicks"""
    id: str = Field(..., description="Click ID")
    tracker_id: str = Field(..., description="Associated tracker ID")
    url: str = Field(..., description="Clicked URL")
    timestamp: datetime = Field(..., description="When the click occurred")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="HTTP referrer")
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "click_550e8400-e29b-41d4-a716-446655440000",
                "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
                "url": "https://example.com/welcome",
                "timestamp": "2025-01-25T10:10:00Z",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ip_address": "192.168.1.1",
                "referrer": "https://gmail.com"
            }
        }


class EmailBounceResponse(BaseModel):
    """Response schema for email bounces"""
    id: str = Field(..., description="Bounce ID")
    tracker_id: str = Field(..., description="Associated tracker ID")
    bounce_type: str = Field(..., description="Type of bounce: hard, soft, complaint")
    bounce_reason: Optional[str] = Field(None, description="Reason for bounce")
    bounce_code: Optional[str] = Field(None, description="SMTP error code")
    timestamp: datetime = Field(..., description="When the bounce occurred")
    raw_message: Optional[str] = Field(None, description="Raw bounce message")
    
    class Config:
        from_attributes = True
        schema_extra = {
            "example": {
                "id": "bounce_550e8400-e29b-41d4-a716-446655440000",
                "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
                "bounce_type": "hard",
                "bounce_reason": "Invalid email address",
                "bounce_code": "550",
                "timestamp": "2025-01-25T10:02:00Z",
                "raw_message": "550 5.1.1 User unknown"
            }
        }


class TrackingPixelResponse(BaseModel):
    """Response schema for tracking pixel debug info"""
    tracker_id: str = Field(..., description="Tracker ID")
    pixel_url: str = Field(..., description="Tracking pixel URL")
    is_valid: bool = Field(..., description="Whether tracker exists")
    
    class Config:
        schema_extra = {
            "example": {
                "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
                "pixel_url": "https://api.emailtracker.com/track/open/550e8400-e29b-41d4-a716-446655440000",
                "is_valid": True
            }
        }


class BotDetectionResponse(BaseModel):
    """Response schema for bot detection analysis"""
    user_agent: str = Field(..., description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    is_bot: bool = Field(..., description="Whether flagged as bot")
    bot_reason: Optional[str] = Field(None, description="Reason for bot detection")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    
    class Config:
        schema_extra = {
            "example": {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "ip_address": "192.168.1.1",
                "is_bot": False,
                "bot_reason": None,
                "confidence": 0.95
            }
        }
