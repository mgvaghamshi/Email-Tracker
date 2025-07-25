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


class ApiKey(Base):
    """API Key model for authentication"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    key_hash = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)  # Friendly name for the key
    user_id = Column(String, nullable=True)  # Optional user association
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Rate limiting fields
    requests_per_minute = Column(Integer, default=100)
    requests_per_day = Column(Integer, default=10000)
    
    __table_args__ = (
        Index('idx_api_key_hash', 'key_hash'),
        Index('idx_api_key_active', 'is_active'),
    )


class EmailTracker(Base):
    """Email tracking model"""
    __tablename__ = "email_trackers"
    
    id = Column(String, primary_key=True)  # UUID tracker ID
    campaign_id = Column(String, nullable=False, index=True)  # UUID campaign ID
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=True)
    
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
    api_key = relationship("ApiKey", backref="email_trackers")
    events = relationship("EmailEvent", back_populates="tracker", cascade="all, delete-orphan")
    clicks = relationship("EmailClick", back_populates="tracker", cascade="all, delete-orphan")
    bounces = relationship("EmailBounce", back_populates="tracker", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_campaign_id', 'campaign_id'),
        Index('idx_recipient_email', 'recipient_email'),
        Index('idx_created_at', 'created_at'),
        Index('idx_sent_at', 'sent_at'),
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
