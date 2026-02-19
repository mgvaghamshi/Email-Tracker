"""
Recurring Campaign models for EmailTracker API - Professional SaaS implementation
"""
import uuid
import json
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, Float, Enum as SQLEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from enum import Enum

from ..models import Base


class RecurringFrequency(str, Enum):
    """Recurring frequency options similar to Mailchimp/ActiveCampaign"""
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    CUSTOM = "custom"  # For custom intervals


class RecurringStatus(str, Enum):
    """Status of recurring campaign series"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DRAFT = "draft"


class WeekDay(str, Enum):
    """Days of the week for weekly scheduling"""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class RecurringCampaign(Base):
    """
    Master recurring campaign configuration
    Similar to Mailchimp's Automation series or ActiveCampaign's Campaigns
    """
    __tablename__ = "recurring_campaigns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    template_id = Column(String, ForeignKey("email_templates.id"), nullable=True)
    
    # Campaign Details
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    subject = Column(String, nullable=False)  # Subject line (can include variables)
    
    # Recurring Configuration
    frequency = Column(SQLEnum(RecurringFrequency), nullable=False)
    custom_interval_days = Column(Integer, nullable=True)  # For custom frequency
    
    # Weekly-specific settings
    send_on_weekdays = Column(Text, nullable=True)  # JSON array of weekdays
    
    # Monthly-specific settings
    monthly_day = Column(Integer, nullable=True)  # Day of month (1-31, 99 for last day)
    monthly_week = Column(Integer, nullable=True)  # Week of month (1-4, 99 for last week)
    monthly_weekday = Column(SQLEnum(WeekDay), nullable=True)  # Weekday for weekly pattern
    
    # Time Configuration
    send_time = Column(String, nullable=False)  # Time in HH:MM format
    timezone = Column(String, default="UTC", nullable=False)
    
    # Scheduling Limits
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=True)  # Optional end date
    max_occurrences = Column(Integer, nullable=True)  # Max number of sends
    
    # Status and Control
    status = Column(SQLEnum(RecurringStatus), default=RecurringStatus.DRAFT, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Recipients Configuration
    recipient_list_id = Column(String, nullable=True)  # Static list
    segment_id = Column(String, nullable=True)  # Dynamic segment
    dynamic_recipients = Column(Boolean, default=False, nullable=False)  # Refresh recipients each send
    
    # Content Configuration
    html_template = Column(Text, nullable=True)
    text_template = Column(Text, nullable=True)
    auto_generate_text = Column(Boolean, default=True, nullable=False)
    
    # Analytics and Tracking
    total_scheduled = Column(Integer, default=0, nullable=False)
    total_sent = Column(Integer, default=0, nullable=False)
    total_failed = Column(Integer, default=0, nullable=False)
    
    # Advanced Settings
    send_rate_limit = Column(Integer, default=1000, nullable=False)  # Emails per hour
    skip_holidays = Column(Boolean, default=False, nullable=False)
    skip_weekends = Column(Boolean, default=False, nullable=False)
    
    # Personalization Settings
    personalization_fields = Column(Text, nullable=True)  # JSON object of custom fields
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sent_at = Column(DateTime, nullable=True)
    next_send_at = Column(DateTime, nullable=True)
    
    # Relationships
    occurrences = relationship("RecurringCampaignOccurrence", back_populates="recurring_campaign", cascade="all, delete-orphan")
    
    def __init__(self, **kwargs):
        # Handle send_on_weekdays conversion to JSON
        if 'send_on_weekdays' in kwargs and isinstance(kwargs['send_on_weekdays'], list):
            kwargs['send_on_weekdays'] = json.dumps(kwargs['send_on_weekdays'])
        
        # Handle personalization_fields conversion to JSON
        if 'personalization_fields' in kwargs and isinstance(kwargs['personalization_fields'], dict):
            kwargs['personalization_fields'] = json.dumps(kwargs['personalization_fields'])
        
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f"<RecurringCampaign(id='{self.id}', name='{self.name}', frequency='{self.frequency}')>"
    
    @property
    def send_weekdays(self) -> List[str]:
        """Get list of weekdays for sending"""
        if self.send_on_weekdays:
            try:
                return json.loads(self.send_on_weekdays)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @send_weekdays.setter
    def send_weekdays(self, value: List[str]):
        """Set weekdays for sending"""
        self.send_on_weekdays = json.dumps(value) if value else None
    
    @property
    def custom_fields(self) -> Dict[str, Any]:
        """Get personalization fields"""
        if self.personalization_fields:
            try:
                return json.loads(self.personalization_fields)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}
    
    @custom_fields.setter
    def custom_fields(self, value: Dict[str, Any]):
        """Set personalization fields"""
        self.personalization_fields = json.dumps(value) if value else None
    
    def calculate_next_send_date(self, from_date: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate the next send date based on frequency and configuration"""
        if not from_date:
            from_date = self.last_sent_at or self.start_date
        
        if not from_date:
            return None
        
        if self.frequency == RecurringFrequency.DAILY:
            next_date = from_date + timedelta(days=1)
        elif self.frequency == RecurringFrequency.WEEKLY:
            next_date = from_date + timedelta(weeks=1)
        elif self.frequency == RecurringFrequency.BIWEEKLY:
            next_date = from_date + timedelta(weeks=2)
        elif self.frequency == RecurringFrequency.MONTHLY:
            # Add one month with proper day handling
            next_date = self._add_months(from_date, 1)
        elif self.frequency == RecurringFrequency.QUARTERLY:
            # Add 3 months with proper day handling
            next_date = self._add_months(from_date, 3)
        elif self.frequency == RecurringFrequency.YEARLY:
            next_date = from_date.replace(year=from_date.year + 1)
        elif self.frequency == RecurringFrequency.CUSTOM and self.custom_interval_days:
            next_date = from_date + timedelta(days=self.custom_interval_days)
        else:
            return None
        
        # Apply time from send_time
        if self.send_time:
            try:
                time_parts = self.send_time.split(":")
                hour = int(time_parts[0])
                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                next_date = next_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except (ValueError, IndexError):
                pass
        
        # Validate that the calculated date is within reasonable bounds
        # PostgreSQL supports dates from 4713 BC to 294276 AD
        # We'll use a reasonable business limit: not more than 50 years in the future
        from datetime import timezone
        
        # Ensure max_date is timezone-aware like next_date should be
        now_utc = datetime.now(timezone.utc)
        max_date = now_utc.replace(year=now_utc.year + 50)
        
        # Ensure next_date is timezone-aware for comparison
        if next_date.tzinfo is None:
            next_date = next_date.replace(tzinfo=timezone.utc)
        elif next_date.tzinfo != timezone.utc:
            next_date = next_date.astimezone(timezone.utc)
            
        if next_date > max_date:
            # Return None to stop scheduling instead of creating invalid dates
            return None
        
        return next_date
    
    def _add_months(self, date: datetime, months: int) -> datetime:
        """
        Safely add months to a date, handling edge cases like Feb 31st.
        Uses last day of month if target day doesn't exist.
        """
        import calendar
        
        # Calculate target year and month
        total_months = date.month + months
        target_year = date.year + (total_months - 1) // 12
        target_month = ((total_months - 1) % 12) + 1
        
        # Get the last day of the target month
        last_day_of_target_month = calendar.monthrange(target_year, target_month)[1]
        
        # Use the original day or the last day of target month, whichever is smaller
        target_day = min(date.day, last_day_of_target_month)
        
        # Create the new date
        return date.replace(year=target_year, month=target_month, day=target_day)
    
    def should_send_today(self, check_date: datetime) -> bool:
        """Check if campaign should send on given date based on frequency rules"""
        if self.frequency == RecurringFrequency.WEEKLY and self.send_weekdays:
            weekday_names = [
                "monday", "tuesday", "wednesday", "thursday", 
                "friday", "saturday", "sunday"
            ]
            current_weekday = weekday_names[check_date.weekday()]
            return current_weekday in self.send_weekdays
        
        if self.skip_weekends and check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Add holiday checking logic here if needed
        if self.skip_holidays:
            # Implement holiday checking logic based on locale
            pass
        
        return True


class RecurringCampaignOccurrence(Base):
    """
    Individual occurrence/instance of a recurring campaign
    Each scheduled send creates one occurrence record
    """
    __tablename__ = "recurring_campaign_occurrences"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    recurring_campaign_id = Column(String, ForeignKey("recurring_campaigns.id"), nullable=False)
    campaign_id = Column(String, ForeignKey("email_campaigns.id"), nullable=True)  # Created campaign for this occurrence
    
    # Occurrence Details
    sequence_number = Column(Integer, nullable=False)  # 1st, 2nd, 3rd occurrence
    scheduled_at = Column(DateTime, nullable=False)
    sent_at = Column(DateTime, nullable=True)  # Match database schema
    
    # Status Tracking
    status = Column(String, default="pending", nullable=False)  # scheduled, sent, failed, skipped, pending
    error_message = Column(Text, nullable=True)
    
    # Recipient Count (no snapshot in database)
    recipients_count = Column(Integer, default=0, nullable=False)
    
    # Performance Metrics
    emails_sent = Column(Integer, default=0, nullable=False)
    emails_delivered = Column(Integer, default=0, nullable=False)
    emails_bounced = Column(Integer, default=0, nullable=False)
    emails_opened = Column(Integer, default=0, nullable=False)
    emails_clicked = Column(Integer, default=0, nullable=False)
    emails_unsubscribed = Column(Integer, default=0, nullable=False)  # Match database schema
    
    # Retry Logic (match database schema)
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    recurring_campaign = relationship("RecurringCampaign", back_populates="occurrences")
    
    def __repr__(self):
        return f"<RecurringCampaignOccurrence(id='{self.id}', sequence={self.sequence_number}, status='{self.status}')>"


# Database indexes for performance
RecurringCampaign.__table_args__ = (
    Index('idx_recurring_user_status', 'user_id', 'status'),
    Index('idx_recurring_next_send', 'next_send_at', 'is_active'),
    Index('idx_recurring_frequency', 'frequency'),
    Index('idx_recurring_created', 'created_at'),
)

RecurringCampaignOccurrence.__table_args__ = (
    Index('idx_occurrence_recurring_id', 'recurring_campaign_id'),
    Index('idx_occurrence_scheduled', 'scheduled_at', 'status'),
    Index('idx_occurrence_sequence', 'recurring_campaign_id', 'sequence_number'),
)
