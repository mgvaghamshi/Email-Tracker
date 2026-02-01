"""
User settings database models for persistent configuration storage
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid
import json
from typing import Dict, Any, Optional

from .models import Base


class UserSettings(Base):
    """User settings model for persistent configuration storage"""
    __tablename__ = "user_settings"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Settings categories stored as JSON
    smtp_settings = Column(Text, nullable=True)  # SMTP configuration
    company_settings = Column(Text, nullable=True)  # Company branding
    security_settings = Column(Text, nullable=True)  # Security preferences
    notification_settings = Column(Text, nullable=True)  # Notification preferences
    storage_settings = Column(Text, nullable=True)  # Storage and retention
    domain_settings = Column(Text, nullable=True)  # Domain configuration
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    __table_args__ = (
        Index('idx_user_settings_user_id', 'user_id'),
        Index('idx_user_settings_updated_at', 'updated_at'),
    )
    
    def get_setting(self, category: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get settings for a specific category"""
        setting_data = getattr(self, f"{category}_settings", None)
        if setting_data:
            try:
                return json.loads(setting_data)
            except (json.JSONDecodeError, TypeError):
                pass
        return default or {}
    
    def set_setting(self, category: str, data: Dict[str, Any]) -> None:
        """Set settings for a specific category"""
        setattr(self, f"{category}_settings", json.dumps(data))
        self.updated_at = datetime.utcnow()
    
    def get_smtp_settings(self) -> Dict[str, Any]:
        """Get SMTP settings with defaults"""
        return self.get_setting("smtp", {
            "server": "",
            "port": 587,
            "security": "TLS",
            "username": "",
            "password": "",
            "isConnected": False
        })
    
    def set_smtp_settings(self, settings: Dict[str, Any]) -> None:
        """Set SMTP settings"""
        self.set_setting("smtp", settings)
    
    def get_company_settings(self) -> Dict[str, Any]:
        """Get company settings with defaults"""
        return self.get_setting("company", {
            "company_name": "Your Company",
            "company_website": "",
            "company_logo": "",
            "company_address": "",
            "support_email": "",
            "privacy_policy_url": "",
            "terms_of_service_url": ""
        })
    
    def set_company_settings(self, settings: Dict[str, Any]) -> None:
        """Set company settings"""
        self.set_setting("company", settings)
    
    def get_security_settings(self) -> Dict[str, Any]:
        """Get security settings with defaults"""
        return self.get_setting("security", {
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30
        })
    
    def set_security_settings(self, settings: Dict[str, Any]) -> None:
        """Set security settings"""
        self.set_setting("security", settings)
    
    def get_notification_settings(self) -> Dict[str, Any]:
        """Get notification settings with defaults"""
        return self.get_setting("notification", {
            "campaignCompletion": True,
            "highBounceRate": True,
            "apiLimitWarnings": True,
            "securityAlerts": True,
            "weeklyReports": False,
            "webhookUrl": "",
            "emailNotifications": True
        })
    
    def set_notification_settings(self, settings: Dict[str, Any]) -> None:
        """Set notification settings"""
        self.set_setting("notification", settings)
    
    def get_storage_settings(self) -> Dict[str, Any]:
        """Get storage settings with defaults"""
        return self.get_setting("storage", {
            "used": 0.0,
            "total": 10.0,
            "retentionPeriod": 12
        })
    
    def set_storage_settings(self, settings: Dict[str, Any]) -> None:
        """Set storage settings"""
        self.set_setting("storage", settings)
    
    def get_domain_settings(self) -> Dict[str, Any]:
        """Get domain settings with defaults"""
        return self.get_setting("domain", {
            "trackingDomain": "",
            "sendingDomain": "",
            "spf": "pending",
            "dkim": "pending"
        })
    
    def set_domain_settings(self, settings: Dict[str, Any]) -> None:
        """Set domain settings"""
        self.set_setting("domain", settings)
    
    def __repr__(self):
        return f"<UserSettings(id={self.id}, user_id={self.user_id})>"


def get_or_create_user_settings(db, user_id: str) -> UserSettings:
    """Get or create user settings for a user"""
    settings = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    if not settings:
        settings = UserSettings(user_id=user_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings
