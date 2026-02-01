"""
Pydantic schemas for Recurring Campaign functionality
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime as DateTime, time
from enum import Enum

from ..database.recurring_models import RecurringFrequency, RecurringStatus, WeekDay
from ..core.datetime_validators import DateTimeValidatorMixin

# Re-export for convenience
Weekday = WeekDay


class RecurringScheduleConfig(BaseModel):
    """Base configuration for recurring schedule"""
    frequency: RecurringFrequency
    custom_interval_days: Optional[int] = None
    
    # Weekly settings
    send_on_weekdays: Optional[List[WeekDay]] = None
    
    # Monthly settings  
    monthly_day: Optional[int] = Field(None, ge=1, le=31)
    monthly_week: Optional[int] = Field(None, ge=1, le=5)  # 5 = last week
    monthly_weekday: Optional[WeekDay] = None
    
    # Time settings - Accept both HH:MM and HH:MM:SS formats
    send_time: str = Field(..., pattern=r'^([01]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?$')
    timezone: str = "UTC"
    
    @validator('send_time')
    def normalize_send_time(cls, v):
        """Normalize send_time to HH:MM format for consistency"""
        if len(v) == 8:  # HH:MM:SS format
            return v[:5]  # Convert to HH:MM
        return v
    
    @validator('custom_interval_days')
    def validate_custom_interval(cls, v, values):
        if values.get('frequency') == RecurringFrequency.CUSTOM and not v:
            raise ValueError('custom_interval_days is required for custom frequency')
        if values.get('frequency') != RecurringFrequency.CUSTOM and v:
            raise ValueError('custom_interval_days only allowed for custom frequency')
        return v
    
    @validator('send_on_weekdays')
    def validate_weekly_settings(cls, v, values):
        if values.get('frequency') == RecurringFrequency.WEEKLY and not v:
            raise ValueError('send_on_weekdays is required for weekly frequency')
        return v


class RecurringCampaignCreate(BaseModel):
    """Schema for creating a new recurring campaign"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    subject_template: str = Field(..., min_length=1, max_length=255)  # This will map to 'subject' in database
    
    # Template and content
    template_id: Optional[str] = None
    html_template: Optional[str] = None
    text_template: Optional[str] = None
    auto_generate_text: bool = True
    
    # Scheduling
    schedule_config: RecurringScheduleConfig
    start_date: Union[str, DateTime]  # Accept both string dates and datetime objects
    end_date: Optional[Union[str, DateTime]] = None  # Accept both string dates and datetime objects
    max_occurrences: Optional[int] = Field(None, ge=1, le=1000)  # Reasonable limit
    
    # Recipients
    recipient_list_id: Optional[str] = None
    segment_id: Optional[str] = None
    dynamic_recipients: bool = False
    
    # Advanced settings
    send_rate_limit: int = Field(1000, ge=100, le=10000)
    skip_holidays: bool = False
    skip_weekends: bool = False
    personalization_fields: Optional[Dict[str, Any]] = None
    
    @validator('start_date', 'end_date', pre=True)
    def normalize_datetime_fields(cls, v):
        """Normalize datetime inputs using our robust datetime validator"""
        if v is None:
            return None
            
        # Reuse our robust datetime normalization logic
        dt_validator = DateTimeValidatorMixin()
        try:
            return dt_validator.normalize_datetime_fields(v)
        except Exception as e:
            raise ValueError(f'Invalid datetime format: {str(e)}')
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        # Import inside function to avoid naming conflicts
        from datetime import datetime as dt_type
        from app.core.datetime_validators import normalize_to_utc_aware
        
        if v is None:
            return v
            
        # Both dates should be normalized by now
        start_dt = values['start_date']
        end_dt = v
        
        if isinstance(end_dt, dt_type) and isinstance(start_dt, dt_type):
            # Normalize both to UTC for safe comparison
            start_utc = normalize_to_utc_aware(start_dt)
            end_utc = normalize_to_utc_aware(end_dt)
            
            # Compare UTC datetime objects
            if end_utc <= start_utc:
                raise ValueError('end_date must be after start_date')
                
        return v
    
    @validator('start_date')
    def validate_start_date(cls, v):
        # Import inside function to avoid naming conflicts
        from datetime import datetime as dt_type
        from app.core.datetime_validators import normalize_to_utc_aware
        import pytz
        
        if not isinstance(v, dt_type):
            return v  # Will be handled by normalization
        
        # Normalize to UTC for comparison
        start_utc = normalize_to_utc_aware(v)
        now_utc = dt_type.now(pytz.UTC)
        
        # Compare UTC datetime objects (allow some buffer for processing time)
        if start_utc.date() < now_utc.date():
            raise ValueError('start_date must be today or in the future')
                
        return v


class RecurringCampaignUpdate(BaseModel):
    """Schema for updating a recurring campaign"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    subject_template: Optional[str] = Field(None, min_length=1, max_length=255)  # This will map to 'subject' in database
    
    # Content updates
    html_template: Optional[str] = None
    text_template: Optional[str] = None
    auto_generate_text: Optional[bool] = None
    
    # Scheduling updates (limited after activation) - Accept flexible datetime formats
    end_date: Optional[Union[str, DateTime]] = None
    max_occurrences: Optional[int] = Field(None, ge=1, le=1000)
    
    # Settings updates
    send_rate_limit: Optional[int] = Field(None, ge=100, le=10000)
    skip_holidays: Optional[bool] = None
    skip_weekends: Optional[bool] = None
    personalization_fields: Optional[Dict[str, Any]] = None
    
    # Status control
    status: Optional[RecurringStatus] = None
    
    @validator('end_date', pre=True)
    def normalize_end_date(cls, v):
        """Normalize datetime inputs using our robust datetime validator"""
        if v is None:
            return None
            
        # Reuse our robust datetime normalization logic
        dt_validator = DateTimeValidatorMixin()
        try:
            return dt_validator.normalize_datetime_fields(v)
        except Exception as e:
            raise ValueError(f'Invalid end_date format: {str(e)}')


class RecurringCampaignResponse(BaseModel):
    """Response schema for recurring campaign"""
    id: str
    name: str
    description: Optional[str]
    subject_template: str = Field(alias='subject')  # Map database 'subject' field to API 'subject_template'
    
    # Scheduling info
    frequency: RecurringFrequency
    custom_interval_days: Optional[int]
    send_on_weekdays: Optional[List[str]]
    send_time: str
    timezone: str
    
    # Dates
    start_date: DateTime
    end_date: Optional[DateTime]
    next_send_at: Optional[DateTime]
    last_sent_at: Optional[DateTime]
    
    # Status
    status: RecurringStatus
    is_active: bool
    
    # Statistics
    total_scheduled: int
    total_sent: int
    total_failed: int
    
    # Configuration
    max_occurrences: Optional[int]
    dynamic_recipients: bool
    skip_holidays: bool
    skip_weekends: bool
    
    # Timestamps
    created_at: DateTime
    updated_at: DateTime
    
    class Config:
        from_attributes = True
        populate_by_name = True
    
    @validator('send_on_weekdays', pre=True)
    def parse_send_on_weekdays(cls, v):
        """Parse JSON string to list if needed"""
        if isinstance(v, str):
            try:
                import json
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        elif isinstance(v, list):
            return v
        return []


class RecurringOccurrenceResponse(BaseModel):
    """Response schema for recurring campaign occurrence"""
    id: str
    recurring_campaign_id: str
    campaign_id: Optional[str]
    sequence_number: int
    
    # Scheduling
    scheduled_at: DateTime
    actual_sent_at: Optional[DateTime]
    
    # Status
    status: str
    error_message: Optional[str]
    
    # Recipients
    recipients_count: int
    
    # Performance
    emails_sent: int
    emails_delivered: int
    emails_bounced: int
    emails_opened: int
    emails_clicked: int
    
    # Calculated metrics
    delivery_rate: Optional[float] = None
    open_rate: Optional[float] = None
    click_rate: Optional[float] = None
    
    # Timestamps
    created_at: DateTime
    updated_at: DateTime
    
    class Config:
        from_attributes = True
        
    @validator('delivery_rate', pre=True, always=True)
    def calculate_delivery_rate(cls, v, values):
        sent = values.get('emails_sent', 0)
        if sent > 0:
            delivered = values.get('emails_delivered', 0)
            return round((delivered / sent) * 100, 2)
        return 0.0
    
    @validator('open_rate', pre=True, always=True)
    def calculate_open_rate(cls, v, values):
        delivered = values.get('emails_delivered', 0)
        if delivered > 0:
            opened = values.get('emails_opened', 0)
            return round((opened / delivered) * 100, 2)
        return 0.0
    
    @validator('click_rate', pre=True, always=True)
    def calculate_click_rate(cls, v, values):
        delivered = values.get('emails_delivered', 0)
        if delivered > 0:
            clicked = values.get('emails_clicked', 0)
            return round((clicked / delivered) * 100, 2)
        return 0.0


class RecurringCampaignListResponse(BaseModel):
    """Response schema for listing recurring campaigns"""
    data: List[RecurringCampaignResponse]
    total: int
    page: int
    limit: int


class RecurringOccurrenceListResponse(BaseModel):
    """Response schema for listing recurring campaign occurrences"""
    data: List[RecurringOccurrenceResponse]
    total: int
    page: int
    limit: int


class RecurringCampaignStatusUpdate(BaseModel):
    """Schema for updating recurring campaign status"""
    status: RecurringStatus
    reason: Optional[str] = None


class RecurringFrequencyOption(BaseModel):
    """Schema for frequency options in UI"""
    value: RecurringFrequency
    label: str
    description: str
    requires_pro: bool = False
    requires_enterprise: bool = False


class RecurringSchedulePreview(BaseModel):
    """Schema for previewing recurring schedule"""
    next_send_dates: List[DateTime]
    total_occurrences: int
    estimated_completion: Optional[DateTime]
    warnings: List[str] = []


class RecurringCampaignAnalytics(BaseModel):
    """Analytics summary for recurring campaign"""
    campaign_id: str
    campaign_name: str
    
    # Overall performance
    total_occurrences: int
    completed_occurrences: int
    failed_occurrences: int
    
    # Aggregate metrics
    total_recipients: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    
    # Average rates
    avg_delivery_rate: float
    avg_open_rate: float
    avg_click_rate: float
    
    # Performance over time
    performance_trend: List[Dict[str, Any]]  # Date-based performance data
    
    # Status
    status: RecurringStatus
    is_active: bool
    next_send_at: Optional[DateTime]
    
    class Config:
        from_attributes = True
