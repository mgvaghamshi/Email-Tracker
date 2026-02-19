from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

# Campaign schemas
class EmailCampaignBase(BaseModel):
    name: str
    description: Optional[str] = None

class EmailCampaignCreate(EmailCampaignBase):
    name: str
    description: Optional[str] = None

class CampaignTrackingResponse(BaseModel):
    id: str
    name: Optional[str]
    company: Optional[str]
    position: Optional[str]
    email: str
    subject: str
    content: Optional[str]
    sent: bool
    created_at: datetime
    updated_at: datetime
    campaign_id: Optional[str]
    campaign_name: Optional[str]
    campaign_description: Optional[str]

    class Config:
        from_attributes = True

class CampaignUpdate(BaseModel):
    sent: Optional[bool] = None
    updated_at: Optional[datetime] = None
    name: Optional[str] = None
    description: Optional[str] = None

class EmailCampaignResponse(EmailCampaignBase):
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    total_sent: int = 0
    total_opens: int = 0
    total_clicks: int = 0
    open_rate: float = 0.0
    click_rate: float = 0.0
    last_email_sent: Optional[datetime] = None

    class Config:
        from_attributes = True

class EmailCampaignWithStats(BaseModel):
    """Extended campaign response with detailed statistics"""
    id: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    total_sent: int
    total_opens: int
    total_clicks: int
    total_bounces: int
    open_rate: float
    click_rate: float
    bounce_rate: float
    last_email_sent: Optional[datetime] = None
    recent_opens: int = 0  # Opens in last 7 days
    recent_clicks: int = 0  # Clicks in last 7 days
    
    class Config:
        from_attributes = True

# Tracker schemas
class EmailTrackerBase(BaseModel):
    recipient_email: EmailStr
    sender_email: EmailStr
    subject: str

class EmailTrackerCreate(EmailTrackerBase):
    campaign_id: str

class EmailTrackerResponse(EmailTrackerBase):
    id: str
    campaign_id: str
    sent_at: datetime
    opened_at: Optional[datetime] = None
    open_count: int
    click_count: int
    delivery_status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Event schemas
class EmailEventResponse(BaseModel):
    id: str
    tracker_id: str
    event_type: str
    timestamp: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    location: Optional[str] = None
    device_type: Optional[str] = None
    
    class Config:
        from_attributes = True

# Email sending schemas
class EmailSendRequest(BaseModel):
    campaign_id: str
    to_email: EmailStr
    to_name: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    from_email: EmailStr
    from_name: Optional[str] = None
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    reply_to: Optional[EmailStr] = None
    attachments: Optional[List[str]] = None  # Base64 encoded attachments

class EmailSendResponse(BaseModel):
    success: bool
    message: str
    tracker_id: Optional[str] = None
    status: Optional[str] = None
    campaign_id: Optional[str] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True

class BulkEmailSendRequest(BaseModel):
    campaign_id: str
    recipients: List[EmailStr]
    from_email: EmailStr
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    reply_to: Optional[EmailStr] = None

# Analytics schemas
class EmailAnalytics(BaseModel):
    campaign_id: str
    total_sent: int
    total_opens: int
    total_clicks: int
    total_bounces: int
    open_rate: float
    click_rate: float
    bounce_rate: float

class DetailedAnalytics(BaseModel):
    campaign_id: str
    total_sent: int
    total_opens: int
    unique_opens: int
    total_clicks: int
    unique_clicks: int
    total_bounces: int
    total_complaints: int
    open_rate: float
    click_rate: float
    bounce_rate: float
    complaint_rate: float
    unsubscribe_rate: float

# Template schemas
class EmailTemplateBase(BaseModel):
    name: str
    subject: str
    html_content: Optional[str] = None
    text_content: Optional[str] = None

class EmailTemplateCreate(EmailTemplateBase):
    pass

class EmailTemplateResponse(EmailTemplateBase):
    id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

# Email list schemas
class EmailListBase(BaseModel):
    name: str
    description: Optional[str] = None

class EmailListCreate(EmailListBase):
    pass

class EmailListResponse(EmailListBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# Subscriber schemas
class EmailSubscriberBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class EmailSubscriberCreate(EmailSubscriberBase):
    email_list_id: str

class EmailSubscriberResponse(EmailSubscriberBase):
    id: str
    email_list_id: str
    is_active: bool
    is_verified: bool
    subscribed_at: datetime
    unsubscribed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Bounce schemas
class EmailBounceResponse(BaseModel):
    id: str
    tracker_id: str
    bounce_type: str
    reason: Optional[str] = None
    timestamp: datetime
    smtp_code: Optional[str] = None
    smtp_message: Optional[str] = None
    
    class Config:
        from_attributes = True

# Click schemas
class EmailClickResponse(BaseModel):
    id: str
    tracker_id: str
    url: str
    timestamp: datetime
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None
    
    class Config:
        from_attributes = True

# Webhook schemas
class WebhookData(BaseModel):
    event_type: str
    tracker_id: str
    timestamp: datetime
    data: dict

class BounceWebhookData(BaseModel):
    tracker_id: str
    bounce_type: str
    reason: Optional[str] = None
    smtp_code: Optional[str] = None
    smtp_message: Optional[str] = None