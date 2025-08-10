"""
Campaign-related Pydantic schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, timezone
import pytz

from .email import EmailTrackerResponse


class CampaignBase(BaseModel):
    """Base campaign schema"""
    name: str = Field(..., max_length=200, description="Campaign name")
    subject: str = Field(..., max_length=200, description="Email subject line")
    description: Optional[str] = Field(None, max_length=1000, description="Campaign description")


class CampaignCreate(CampaignBase):
    """Schema for creating a new campaign"""
    pass


class CampaignUpdate(BaseModel):
    """Schema for updating a campaign"""
    name: Optional[str] = Field(None, max_length=200, description="Campaign name")
    subject: Optional[str] = Field(None, max_length=200, description="Email subject line")
    description: Optional[str] = Field(None, max_length=1000, description="Campaign description")
    status: Optional[str] = Field(None, description="Campaign status")


class CampaignSchedule(BaseModel):
    """Schema for scheduling a campaign"""
    scheduled_at: datetime = Field(..., description="When to send the campaign")
    timezone: Optional[str] = Field("UTC", description="Timezone for the scheduled time (e.g., 'America/New_York', 'Europe/London')")
    
    @validator('timezone')
    def validate_timezone(cls, v):
        """Validate that the timezone is a valid IANA timezone"""
        if v is None:
            return "UTC"
        
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f'Invalid timezone: {v}. Please use IANA timezone names like "America/New_York" or "Europe/London"')
    
    @validator('scheduled_at')
    def validate_future_time(cls, v, values):
        """Validate that the scheduled time is in the future"""
        # Get timezone from values
        tz_name = values.get('timezone', 'UTC')
        
        try:
            # Get timezone object
            if tz_name == 'UTC':
                tz = timezone.utc
            else:
                tz = pytz.timezone(tz_name)
            
            # Convert current time to the specified timezone for comparison
            now_in_tz = datetime.now(tz)
            
            # If the incoming datetime is timezone-naive, assume it's in the specified timezone
            if v.tzinfo is None:
                v_with_tz = tz.localize(v) if hasattr(tz, 'localize') else v.replace(tzinfo=tz)
            else:
                v_with_tz = v.astimezone(tz)
            
            if v_with_tz <= now_in_tz:
                raise ValueError('Scheduled time must be in the future')
            
            return v
        except Exception as e:
            if "must be in the future" in str(e):
                raise e
            # If timezone validation fails, fall back to UTC comparison
            now_utc = datetime.now(timezone.utc)
            if v.tzinfo is None:
                v = v.replace(tzinfo=timezone.utc)
            if v <= now_utc:
                raise ValueError('Scheduled time must be in the future')
            return v


class Campaign(CampaignBase):
    """Campaign response schema"""
    id: str = Field(..., description="Unique campaign identifier")
    status: str = Field(..., description="Campaign status (draft, active, completed, paused, scheduled)")
    recipients_count: int = Field(0, description="Total number of recipients")
    sent_count: int = Field(0, description="Number of emails sent")
    open_rate: float = Field(0.0, description="Open rate percentage")
    click_rate: float = Field(0.0, description="Click rate percentage")
    created_at: datetime = Field(..., description="Campaign creation timestamp")
    sent_at: Optional[datetime] = Field(None, description="Campaign send timestamp")
    scheduled_at: Optional[datetime] = Field(None, description="Campaign scheduled timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "campaign-123",
                "name": "Newsletter January 2025",
                "subject": "Welcome to our monthly newsletter!",
                "description": "Monthly newsletter with product updates and news",
                "status": "completed",
                "recipients_count": 1000,
                "sent_count": 985,
                "open_rate": 24.5,
                "click_rate": 3.2,
                "created_at": "2025-01-01T10:00:00Z",
                "sent_at": "2025-01-01T14:30:00Z"
            }
        }


class CampaignStats(BaseModel):
    """Detailed campaign statistics"""
    total_emails: int = Field(..., description="Total emails in campaign")
    delivered: int = Field(..., description="Successfully delivered emails")
    opened: int = Field(..., description="Emails opened")
    clicked: int = Field(..., description="Emails with clicks")
    bounced: int = Field(..., description="Bounced emails")
    unsubscribed: int = Field(..., description="Unsubscribed recipients")
    open_rate: float = Field(..., description="Open rate percentage")
    click_rate: float = Field(..., description="Click rate percentage")
    bounce_rate: float = Field(..., description="Bounce rate percentage")
    unsubscribe_rate: float = Field(..., description="Unsubscribe rate percentage")

    class Config:
        json_schema_extra = {
            "example": {
                "total_emails": 1000,
                "delivered": 985,
                "opened": 245,
                "clicked": 32,
                "bounced": 15,
                "unsubscribed": 3,
                "open_rate": 24.5,
                "click_rate": 3.2,
                "bounce_rate": 1.5,
                "unsubscribe_rate": 0.3
            }
        }


class CampaignResponse(BaseModel):
    """Detailed campaign response with statistics"""
    campaign: Campaign
    stats: CampaignStats
    trackers: List[EmailTrackerResponse] = Field([], description="Sample email trackers")


class CampaignList(BaseModel):
    """Paginated list of campaigns"""
    data: List[Campaign] = Field(..., description="List of campaigns")
    total: int = Field(..., description="Total number of campaigns")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")

    class Config:
        json_schema_extra = {
            "example": {
                "data": [
                    {
                        "id": "campaign-123",
                        "name": "Newsletter January 2025",
                        "subject": "Welcome to our monthly newsletter!",
                        "status": "completed",
                        "recipients_count": 1000,
                        "sent_count": 985,
                        "open_rate": 24.5,
                        "click_rate": 3.2,
                        "created_at": "2025-01-01T10:00:00Z",
                        "sent_at": "2025-01-01T14:30:00Z"
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 50
            }
        }
