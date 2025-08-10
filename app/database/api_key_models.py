"""
Enhanced API Key models for secure, user-based authentication
"""
from sqlalchemy import (
    Column, String, Boolean, Integer, DateTime, Text,
    ForeignKey, Index, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
import uuid
import json
from datetime import datetime
from typing import List, Optional

# Create a separate Base for API key models to avoid conflicts
Base = declarative_base()


class ApiKey(Base):
    """Enhanced API Key model with user-based scoping and security"""
    __tablename__ = "api_keys"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)  # Required user association
    
    # Key information
    name = Column(String, nullable=False)  # Friendly name for the key
    hashed_key = Column(String, nullable=False, unique=True, index=True)  # bcrypt hashed key
    prefix = Column(String, nullable=False)  # First 8 chars for identification (emt_xxxxxxxx)
    
    # Scopes and permissions (stored as JSON string)
    scopes = Column(Text, nullable=False, default='[]')  # JSON: ['emails:send', 'campaigns:read', etc.]
    
    # Status and lifecycle
    is_active = Column(Boolean, default=True, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime, nullable=True)
    revoked_reason = Column(String, nullable=True)
    
    # Rate limiting
    requests_per_minute = Column(Integer, default=100, nullable=False)
    requests_per_day = Column(Integer, default=10000, nullable=False)
    
    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    
    # Expiration
    expires_at = Column(DateTime, nullable=True)
    
    # Audit fields
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String, nullable=True)  # User ID who created this key
    
    # Relationships
    usage_records = relationship("ApiKeyUsage", back_populates="api_key", cascade="all, delete-orphan")
    
    # Properties for scope handling
    @property
    def scope_list(self) -> List[str]:
        """Get scopes as a list"""
        if self.scopes:
            try:
                return json.loads(self.scopes)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @scope_list.setter
    def scope_list(self, value: List[str]):
        """Set scopes from a list"""
        self.scopes = json.dumps(value) if value else '[]'
    
    def has_scope(self, scope: str) -> bool:
        """Check if API key has a specific scope"""
        return scope in self.scope_list
    
    def has_any_scope(self, scopes: List[str]) -> bool:
        """Check if API key has any of the specified scopes"""
        key_scopes = self.scope_list
        return any(scope in key_scopes for scope in scopes)
    
    def has_all_scopes(self, scopes: List[str]) -> bool:
        """Check if API key has all of the specified scopes"""
        key_scopes = self.scope_list
        return all(scope in key_scopes for scope in scopes)
    
    def is_valid(self) -> bool:
        """Check if the API key is valid and can be used"""
        if not self.is_active or self.revoked:
            return False
        
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
            
        return True
    
    def update_usage(self):
        """Update last used timestamp and usage count"""
        self.last_used_at = datetime.utcnow()
        self.usage_count += 1
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_api_key_user_id', 'user_id'),
        Index('idx_api_key_prefix', 'prefix'),
        Index('idx_api_key_active', 'is_active'),
        Index('idx_api_key_revoked', 'revoked'),
        Index('idx_api_key_expires_at', 'expires_at'),
        Index('idx_api_key_last_used', 'last_used_at'),
        Index('idx_api_key_created_at', 'created_at'),
    )


class ApiKeyUsage(Base):
    """API Key usage tracking and analytics"""
    __tablename__ = "api_key_usage"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id = Column(String, ForeignKey("api_keys.id"), nullable=False)
    
    # Request information
    endpoint = Column(String, nullable=False)  # '/api/v1/emails/send'
    method = Column(String, nullable=False)    # 'POST', 'GET', etc.
    status_code = Column(Integer, nullable=False)  # HTTP response status
    response_time_ms = Column(Integer, nullable=True)  # Response time in milliseconds
    
    # Client information
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String, nullable=True)  # Request correlation ID
    
    # Timing
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Error information (if any)
    error_code = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Request size (optional)
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # Relationships
    api_key = relationship("ApiKey", back_populates="usage_records")
    
    # Table constraints and indexes
    __table_args__ = (
        Index('idx_usage_api_key_id', 'api_key_id'),
        Index('idx_usage_timestamp', 'timestamp'),
        Index('idx_usage_endpoint', 'endpoint'),
        Index('idx_usage_status_code', 'status_code'),
        Index('idx_usage_api_key_timestamp', 'api_key_id', 'timestamp'),
        Index('idx_usage_ip_address', 'ip_address'),
    )
