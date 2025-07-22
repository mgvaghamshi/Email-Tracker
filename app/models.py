from sqlalchemy import Column, String, DateTime, Integer, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class EmailCampaign(Base):
    __tablename__ = "email_campaigns"
    
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Add relationship to trackers - THIS IS THE KEY ADDITION
    email_trackers = relationship("EmailTracker", back_populates="campaign")
    
    # Add helper methods for statistics
    @property
    def total_sent(self):
        return len(self.email_trackers)
    
    @property
    def total_opens(self):
        return sum(1 for tracker in self.email_trackers if tracker.opened_at)
    
    @property
    def total_clicks(self):
        return sum(tracker.click_count for tracker in self.email_trackers)
    
    @property
    def open_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_opens / self.total_sent) * 100, 2)
    
    @property
    def click_rate(self):
        if self.total_sent == 0:
            return 0
        return round((self.total_clicks / self.total_sent) * 100, 2)

class EmailTracker(Base):
    __tablename__ = "email_trackers"
    
    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey("email_campaigns.id"), nullable=True)
    name = Column(String)
    company = Column(String)
    position = Column(String)
    email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text)
    delivered = Column(Boolean, default=False)
    recipient_email = Column(String, nullable=False)
    sender_email = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    opened_at = Column(DateTime, nullable=True)
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    
    # Add back reference to campaign - THIS IS IMPORTANT
    campaign = relationship("EmailCampaign", back_populates="email_trackers")
    
    # Relationships to other models
    events = relationship("EmailEvent", back_populates="tracker")
    bounces = relationship("EmailBounce", back_populates="tracker")
    clicks = relationship("EmailClick", back_populates="tracker")

class EmailEvent(Base):
    __tablename__ = "email_events"
    
    id = Column(String, primary_key=True)
    tracker_id = Column(String, ForeignKey("email_trackers.id"))
    event_type = Column(String, nullable=False)  # open, click, bounce, etc.
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_agent = Column(Text)
    ip_address = Column(String)
    
    tracker = relationship("EmailTracker", back_populates="events")

class EmailClick(Base):
    __tablename__ = "email_clicks"
    
    id = Column(String, primary_key=True)
    tracker_id = Column(String, ForeignKey("email_trackers.id"))
    url = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    tracker = relationship("EmailTracker", back_populates="clicks")

class EmailBounce(Base):
    __tablename__ = "email_bounces"
    
    id = Column(String, primary_key=True)
    tracker_id = Column(String, ForeignKey("email_trackers.id"))
    bounce_type = Column(String)  # hard, soft
    reason = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    tracker = relationship("EmailTracker", back_populates="bounces")

class EmailTemplate(Base):
    __tablename__ = "email_templates"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    html_content = Column(Text)
    text_content = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)

class EmailList(Base):
    __tablename__ = "email_lists"
    
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subscribers = relationship("EmailSubscriber", back_populates="email_list")

class EmailSubscriber(Base):
    __tablename__ = "email_subscribers"
    
    id = Column(String, primary_key=True, index=True)
    email_list_id = Column(String, ForeignKey("email_lists.id"), nullable=False)
    email = Column(String, nullable=False, index=True)
    first_name = Column(String)
    last_name = Column(String)
    
    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Metadata
    subscribed_at = Column(DateTime, default=datetime.utcnow)
    unsubscribed_at = Column(DateTime, nullable=True)
    
    # Relationships
    email_list = relationship("EmailList", back_populates="subscribers")