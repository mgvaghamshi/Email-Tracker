"""
Contact schemas for request/response validation
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ContactBase(BaseModel):
    """Base contact schema"""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str = Field(default="active", pattern="^(active|unsubscribed|bounced)$")
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ContactCreate(ContactBase):
    """Schema for creating a new contact"""
    pass


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|unsubscribed|bounced)$")
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ContactResponse(ContactBase):
    """Schema for contact response"""
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    last_activity: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class ContactList(BaseModel):
    """Schema for paginated contact list response"""
    data: List[ContactResponse]
    total: int
    page: int
    limit: int
    pages: int


class ContactStats(BaseModel):
    """Contact statistics schema"""
    total_contacts: int
    active_contacts: int
    unsubscribed_contacts: int
    bounced_contacts: int
    recent_contacts_count: int  # Contacts added in last 30 days
