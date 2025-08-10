"""
Database models for EmailTracker API
"""
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from .connection import Base


class CampaignVersion(Base):
    """Campaign version history for tracking changes"""
    __tablename__ = "campaign_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Version information
    version_number = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Content snapshots
    email_html = Column(Text, nullable=True)
    email_text = Column(Text, nullable=True)
    
    # Recipient list snapshot (JSON string of recipient IDs)
    recipient_list = Column(Text, nullable=True)
    
    # Change tracking
    changes_summary = Column(Text, nullable=True)
    modified_by = Column(String, nullable=False)  # User email who made the changes
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    campaign = relationship("Campaign", backref="versions")
    user = relationship("User", backref="campaign_versions")
    
    __table_args__ = (
        Index('idx_campaign_version_campaign', 'campaign_id'),
        Index('idx_campaign_version_number', 'campaign_id', 'version_number'),
        Index('idx_campaign_version_created', 'created_at'),
        UniqueConstraint('campaign_id', 'version_number', name='unique_campaign_version'),
    )


# Legacy API Key models - moved to api_key_models.py
# The enhanced versions provide better security and features
"""
class ApiKey(Base):
    # DEPRECATED: Use app.database.api_key_models.ApiKey instead
    pass

class ApiKeyUsage(Base):
    # DEPRECATED: Use app.database.api_key_models.ApiKeyUsage instead
    pass
"""


class Campaign(Base):
    """Campaign model for email campaigns"""
    __tablename__ = "campaigns"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)  # Deprecated
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user_id for data isolation
    template_id = Column(String, ForeignKey("templates.id"), nullable=True)  # Link to template
    
    # Campaign details
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Campaign status: draft, scheduled, sending, completed, paused
    status = Column(String, default="draft", nullable=False)
    
    # Statistics
    recipients_count = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scheduled_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    
    # Timezone for scheduled campaigns (IANA timezone name like 'America/New_York')
    timezone = Column(String(100), default="UTC", nullable=True)
    
    # Relationships
    # api_key = relationship("ApiKey", backref="campaigns")  # Deprecated
    user = relationship("User", back_populates="campaigns")
    template = relationship("Template", backref="campaigns")
    trackers = relationship("EmailTracker", 
                          foreign_keys="EmailTracker.campaign_id",
                          primaryjoin="Campaign.id == foreign(EmailTracker.campaign_id)",
                          backref="campaign")
    
    __table_args__ = (
        # Primary indexes
        Index('idx_campaign_status', 'status'),
        Index('idx_campaign_created_at', 'created_at'),
        Index('idx_campaign_user_id', 'user_id'),
        Index('idx_campaign_template_id', 'template_id'),
        
        # Performance indexes for analytics
        Index('idx_user_status', 'user_id', 'status'),
        Index('idx_user_created', 'user_id', 'created_at'),
        Index('idx_status_sent', 'status', 'sent_count'),
    )


class CampaignRecipient(Base):
    """Campaign recipients junction table"""
    __tablename__ = "campaign_recipients"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    campaign_id = Column(String, ForeignKey("campaigns.id"), nullable=False)
    contact_id = Column(String, ForeignKey("contacts.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    contact = relationship("Contact", backref="campaign_recipients")
    
    __table_args__ = (
        # Ensure unique campaign-contact pairs
        UniqueConstraint('campaign_id', 'contact_id', name='unique_campaign_contact'),
        Index('idx_campaign_recipients_campaign', 'campaign_id'),
        Index('idx_campaign_recipients_contact', 'contact_id'),
        Index('idx_campaign_recipients_user', 'user_id'),
    )


class EmailTracker(Base):
    """Email tracking model"""
    __tablename__ = "email_trackers"
    
    id = Column(String, primary_key=True)  # UUID tracker ID
    campaign_id = Column(String, nullable=False, index=True)  # UUID campaign ID
    # api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)  # Deprecated
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user_id for data isolation
    
    # Email details
    recipient_email = Column(String, nullable=False, index=True)
    sender_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    html_content = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)
    
    # Status tracking
    delivered = Column(Boolean, default=False)
    bounced = Column(Boolean, default=False)
    complained = Column(Boolean, default=False)
    unsubscribed = Column(Boolean, default=False)
    
    # Engagement tracking
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    unique_opens = Column(Integer, default=0)
    unique_clicks = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)  # First open
    first_click_at = Column(DateTime, nullable=True)
    scheduled_at = Column(DateTime, nullable=True)
    
    # Relationships
    # api_key = relationship("ApiKey", backref="email_trackers")  # Deprecated
    user = relationship("User", back_populates="email_trackers")
    events = relationship("EmailEvent", back_populates="tracker", cascade="all, delete-orphan")
    clicks = relationship("EmailClick", back_populates="tracker", cascade="all, delete-orphan")
    bounces = relationship("EmailBounce", back_populates="tracker", cascade="all, delete-orphan")
    
    __table_args__ = (
        # Primary indexes for frequent queries
        Index('idx_campaign_id', 'campaign_id'),
        Index('idx_recipient_email', 'recipient_email'),
        Index('idx_created_at', 'created_at'),
        Index('idx_sent_at', 'sent_at'),
        Index('idx_email_tracker_user_id', 'user_id'),
        
        # Performance indexes for analytics queries
        Index('idx_user_campaign', 'user_id', 'campaign_id'),
        Index('idx_delivered_opened', 'delivered', 'open_count'),
        Index('idx_delivered_clicked', 'delivered', 'click_count'),
        Index('idx_status_fields', 'delivered', 'bounced', 'complained'),
        Index('idx_engagement_stats', 'open_count', 'click_count'),
        Index('idx_timeline_analytics', 'user_id', 'created_at'),
        Index('idx_campaign_analytics', 'campaign_id', 'delivered', 'open_count', 'click_count'),
    )


class EmailEvent(Base):
    """Email event tracking (opens, clicks, etc.)"""
    __tablename__ = "email_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tracker_id = Column(String, ForeignKey("email_trackers.id"), nullable=False)
    
    event_type = Column(String, nullable=False)  # 'open', 'click', 'bounce', 'complaint'
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Request details
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    
    # Geolocation data (optional)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    
    # Device/client detection
    device_type = Column(String, nullable=True)  # 'desktop', 'mobile', 'tablet'
    client_name = Column(String, nullable=True)  # Email client name
    client_version = Column(String, nullable=True)
    
    # Bot detection
    is_bot = Column(Boolean, default=False)
    bot_reason = Column(String, nullable=True)
    
    # Relationships
    tracker = relationship("EmailTracker", back_populates="events")
    
    __table_args__ = (
        Index('idx_tracker_id', 'tracker_id'),
        Index('idx_event_type', 'event_type'),
        Index('idx_timestamp', 'timestamp'),
        Index('idx_tracker_event_type', 'tracker_id', 'event_type'),
    )


class EmailClick(Base):
    """Email click tracking"""
    __tablename__ = "email_clicks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tracker_id = Column(String, ForeignKey("email_trackers.id"), nullable=False)
    
    url = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Request details
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String, nullable=True)
    referrer = Column(Text, nullable=True)
    
    # Relationships
    tracker = relationship("EmailTracker", back_populates="clicks")
    
    __table_args__ = (
        Index('idx_click_tracker_id', 'tracker_id'),
        Index('idx_click_timestamp', 'timestamp'),
        Index('idx_click_url', 'url'),
    )


class EmailBounce(Base):
    """Email bounce tracking"""
    __tablename__ = "email_bounces"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tracker_id = Column(String, ForeignKey("email_trackers.id"), nullable=False)
    
    bounce_type = Column(String, nullable=False)  # 'hard', 'soft', 'complaint'
    bounce_reason = Column(Text, nullable=True)
    bounce_code = Column(String, nullable=True)  # SMTP error code
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Raw bounce data
    raw_message = Column(Text, nullable=True)
    
    # Relationships
    tracker = relationship("EmailTracker", back_populates="bounces")
    
    __table_args__ = (
        Index('idx_bounce_tracker_id', 'tracker_id'),
        Index('idx_bounce_type', 'bounce_type'),
        Index('idx_bounce_timestamp', 'timestamp'),
    )


class WebhookEvent(Base):
    """Webhook event log"""
    __tablename__ = "webhook_events"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    webhook_url = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(Text, nullable=False)  # JSON payload
    
    # Delivery tracking
    delivered = Column(Boolean, default=False)
    delivery_attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)
    next_attempt_at = Column(DateTime, nullable=True)
    
    # Response tracking
    response_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_webhook_url', 'webhook_url'),
        Index('idx_webhook_event_type', 'event_type'),
        Index('idx_webhook_delivered', 'delivered'),
    )


class Contact(Base):
    """Contact model for managing email recipients"""
    __tablename__ = "contacts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=False)  # Deprecated
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user_id for data isolation
    
    # Contact details
    email = Column(String, nullable=False, index=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    
    # Status: active, unsubscribed, bounced
    status = Column(String, default="active", nullable=False)
    
    # Metadata
    tags = Column(Text, nullable=True)  # JSON array of tags
    custom_fields = Column(Text, nullable=True)  # JSON object for custom fields
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activity = Column(DateTime, nullable=True)
    
    # Relationships
    # api_key = relationship("ApiKey", backref="contacts")  # Deprecated
    user = relationship("User", back_populates="contacts")
    
    __table_args__ = (
        # UniqueConstraint('api_key_id', 'email', name='uix_api_key_email'),  # Deprecated
        UniqueConstraint('user_id', 'email', name='uix_user_email'),  # Updated for user-based model
        Index('idx_contact_email', 'email'),
        Index('idx_contact_status', 'status'),
        # Index('idx_contact_api_key', 'api_key_id'),  # Deprecated
        Index('idx_contact_user_id', 'user_id'),  # Updated for user-based model
        Index('idx_contact_created_at', 'created_at'),
    )


class Template(Base):
    """Template model for email templates"""
    __tablename__ = "templates"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=False)  # Deprecated
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Add user_id for data isolation
    
    # Template details
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # newsletter, promotional, transactional, welcome
    status = Column(String, default="draft", nullable=False)  # draft, published, archived
    
    # Template content
    subject = Column(String, nullable=True)
    html_content = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)
    
    # Metadata
    description = Column(Text, nullable=True)
    thumbnail_url = Column(String, nullable=True)
    usage_count = Column(Integer, default=0)
    
    # Premium Features
    tags = Column(Text, nullable=True)  # Comma-separated tags
    folder = Column(String, nullable=True)  # Template folder/category
    is_locked = Column(Boolean, default=False)  # Template locking for collaboration
    locked_by = Column(String, nullable=True)  # User ID who locked the template
    locked_at = Column(DateTime, nullable=True)  # When template was locked
    version = Column(Integer, default=1)  # Version number for versioning
    parent_template_id = Column(String, nullable=True)  # For A/B variations
    is_system_template = Column(Boolean, default=False)  # Pre-built templates flag
    last_used_at = Column(DateTime, nullable=True)  # Last time template was used
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    # api_key = relationship("ApiKey", backref="templates")  # Deprecated
    user = relationship("User", back_populates="templates")
    
    __table_args__ = (
        # Index('idx_template_api_key', 'api_key_id'),  # Deprecated
        Index('idx_template_user', 'user_id'),
        Index('idx_template_type', 'type'),
        Index('idx_template_status', 'status'),
        Index('idx_template_created_at', 'created_at'),
        Index('idx_template_folder', 'folder'),
        Index('idx_template_system', 'is_system_template'),
        Index('idx_template_parent', 'parent_template_id'),
    )


class TemplateVersion(Base):
    """Template version history for tracking changes"""
    __tablename__ = "template_versions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    template_id = Column(String, ForeignKey("templates.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Version details
    version_number = Column(Integer, nullable=False)
    change_summary = Column(Text, nullable=True)
    
    # Snapshot of template content at this version
    name = Column(String, nullable=False)
    subject = Column(String, nullable=True)
    html_content = Column(Text, nullable=True)
    text_content = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    # Tracking
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    template = relationship("Template", backref="versions")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_template_version_template', 'template_id'),
        Index('idx_template_version_user', 'user_id'),
        Index('idx_template_version_created', 'created_at'),
    )
