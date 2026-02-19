"""
API Key database model for authentication
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from ..models import Base


class ApiKey(Base):
    """API keys for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)  # Friendly name for the key
    key_hash = Column(String, nullable=False)  # Hashed API key
    key_prefix = Column(String, nullable=False)  # First 8 chars for identification (e.g., "et_12345678")
    
    # Rate limiting
    requests_per_minute = Column(Integer, default=100)
    requests_per_day = Column(Integer, default=10000)
    
    # Status
    is_active = Column(Boolean, default=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, nullable=True)
    
    # Usage tracking (stored separately in ApiKeyUsage)
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_api_keys_user_id', 'user_id'),
        Index('idx_api_keys_key_hash', 'key_hash'),
        Index('idx_api_keys_key_prefix', 'key_prefix'),
        Index('idx_api_keys_is_active', 'is_active'),
    )
    
    def is_valid(self) -> bool:
        """Check if API key is valid"""
        if not self.is_active:
            return False
        if self.expires_at and datetime.utcnow() > self.expires_at:
            return False
        return True


class ApiKeyUsage(Base):
    """API key usage tracking"""
    __tablename__ = "api_key_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=False)
    
    # Time window for tracking
    window_start = Column(DateTime, nullable=False)  # Start of minute/day window
    window_type = Column(String, nullable=False)  # 'minute' or 'day'
    
    # Usage counts
    request_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Indexes for better performance
    __table_args__ = (
        Index('idx_api_key_usage_api_key_id', 'api_key_id'),
        Index('idx_api_key_usage_window', 'api_key_id', 'window_type', 'window_start'),
    )
