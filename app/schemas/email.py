"""
Email-related Pydantic schemas
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


class EmailSendRequest(BaseModel):
    """Request schema for sending an email"""
    to_email: EmailStr = Field(..., description="Recipient email address")
    from_email: EmailStr = Field(..., description="Sender email address")
    from_name: Optional[str] = Field(None, description="Sender display name")
    subject: str = Field(..., max_length=200, description="Email subject line")
    html_content: Optional[str] = Field(None, description="HTML email content")
    text_content: Optional[str] = Field(None, description="Plain text email content")
    reply_to: Optional[EmailStr] = Field(None, description="Reply-to email address")
    scheduled_at: Optional[datetime] = Field(None, description="Schedule email for later delivery")
    campaign_id: Optional[str] = Field(None, description="Optional campaign ID for grouping")
    
    @validator('html_content', 'text_content')
    def validate_content(cls, v, values):
        if not v and not values.get('html_content') and not values.get('text_content'):
            raise ValueError('Either html_content or text_content must be provided')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "to_email": "user@example.com",
                "from_email": "sender@company.com",
                "from_name": "Company Name",
                "subject": "Welcome to our service!",
                "html_content": "<h1>Welcome!</h1><p>Thank you for signing up.</p>",
                "text_content": "Welcome! Thank you for signing up.",
                "reply_to": "support@company.com"
            }
        }


class BulkEmailSendRequest(BaseModel):
    """Request schema for sending bulk emails"""
    recipients: List[EmailStr] = Field(..., min_items=1, max_items=1000, description="List of recipient email addresses")
    from_email: EmailStr = Field(..., description="Sender email address")
    from_name: Optional[str] = Field(None, description="Sender display name")
    subject: str = Field(..., max_length=200, description="Email subject line")
    html_content: Optional[str] = Field(None, description="HTML email content")
    text_content: Optional[str] = Field(None, description="Plain text email content")
    reply_to: Optional[EmailStr] = Field(None, description="Reply-to email address")
    campaign_id: Optional[str] = Field(None, description="Optional campaign ID for grouping")
    
    @validator('html_content', 'text_content')
    def validate_content(cls, v, values):
        if not v and not values.get('html_content') and not values.get('text_content'):
            raise ValueError('Either html_content or text_content must be provided')
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "recipients": ["user1@example.com", "user2@example.com"],
                "from_email": "sender@company.com",
                "from_name": "Company Name",
                "subject": "Monthly Newsletter",
                "html_content": "<h1>Newsletter</h1><p>Check out this month's updates!</p>",
                "campaign_id": "newsletter-2025-01"
            }
        }


class EmailSendResponse(BaseModel):
    """Response schema for email sending"""
    success: bool = Field(..., description="Whether the email was successfully queued")
    message: str = Field(..., description="Response message")
    tracker_id: Optional[str] = Field(None, description="Unique tracking ID for this email")
    campaign_id: Optional[str] = Field(None, description="Campaign ID for this email")
    status: str = Field(..., description="Email status: queued, scheduled, failed")
    error: Optional[str] = Field(None, description="Error message if failed")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Email queued successfully for user@example.com",
                "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
                "campaign_id": "campaign_550e8400-e29b-41d4-a716-446655440001",
                "status": "queued"
            }
        }


class EmailTrackerResponse(BaseModel):
    """Response schema for email tracker information"""
    id: str = Field(..., description="Tracker ID")
    campaign_id: str = Field(..., description="Campaign ID")
    recipient_email: str = Field(..., description="Recipient email address")
    sender_email: str = Field(..., description="Sender email address")
    subject: str = Field(..., description="Email subject")
    
    # Status
    delivered: bool = Field(..., description="Whether email was delivered")
    bounced: bool = Field(..., description="Whether email bounced")
    complained: bool = Field(..., description="Whether recipient complained")
    unsubscribed: bool = Field(..., description="Whether recipient unsubscribed")
    
    # Engagement
    open_count: int = Field(..., description="Number of times email was opened")
    click_count: int = Field(..., description="Number of times links were clicked")
    unique_opens: int = Field(..., description="Number of unique opens")
    unique_clicks: int = Field(..., description="Number of unique clicks")
    
    # Timestamps
    created_at: datetime = Field(..., description="When email was created")
    sent_at: Optional[datetime] = Field(None, description="When email was sent")
    delivered_at: Optional[datetime] = Field(None, description="When email was delivered")
    opened_at: Optional[datetime] = Field(None, description="When email was first opened")
    first_click_at: Optional[datetime] = Field(None, description="When first link was clicked")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "campaign_id": "campaign_550e8400-e29b-41d4-a716-446655440001",
                "recipient_email": "user@example.com",
                "sender_email": "sender@company.com",
                "subject": "Welcome to our service!",
                "delivered": True,
                "bounced": False,
                "complained": False,
                "unsubscribed": False,
                "open_count": 3,
                "click_count": 1,
                "unique_opens": 1,
                "unique_clicks": 1,
                "created_at": "2025-01-25T10:00:00Z",
                "sent_at": "2025-01-25T10:01:00Z",
                "delivered_at": "2025-01-25T10:02:00Z",
                "opened_at": "2025-01-25T10:05:00Z",
                "first_click_at": "2025-01-25T10:10:00Z"
            }
        }
