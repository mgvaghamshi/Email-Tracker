"""
Template schemas for request/response models
"""
from pydantic import BaseModel, Field, computed_field
from typing import Optional, List
from datetime import datetime


class TemplateBase(BaseModel):
    name: str = Field(..., description="Template name")
    type: str = Field(..., description="Template type (newsletter, promotional, transactional, welcome)")
    status: str = Field(default="draft", description="Template status (draft, published, archived)")
    subject: Optional[str] = Field(None, description="Email subject line")
    html_content: Optional[str] = Field(None, description="HTML content of the template")
    text_content: Optional[str] = Field(None, description="Plain text content of the template")
    description: Optional[str] = Field(None, description="Template description")
    thumbnail_url: Optional[str] = Field(None, description="Template thumbnail URL")
    # Premium Features
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    folder: Optional[str] = Field(None, description="Template folder/category")


class TemplateCreate(TemplateBase):
    """Schema for creating a new template"""
    pass


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template"""
    name: Optional[str] = Field(None, description="Template name")
    type: Optional[str] = Field(None, description="Template type")
    status: Optional[str] = Field(None, description="Template status")
    subject: Optional[str] = Field(None, description="Email subject line")
    html_content: Optional[str] = Field(None, description="HTML content")
    text_content: Optional[str] = Field(None, description="Plain text content")
    description: Optional[str] = Field(None, description="Template description")
    thumbnail_url: Optional[str] = Field(None, description="Template thumbnail URL")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    folder: Optional[str] = Field(None, description="Template folder/category")
    change_summary: Optional[str] = Field(None, description="Summary of changes for version history")


class TemplateResponse(TemplateBase):
    """Schema for template responses"""
    id: str
    user_id: str
    usage_count: int
    version: int
    is_locked: bool
    locked_by: Optional[str]
    locked_at: Optional[datetime]
    parent_template_id: Optional[str]
    is_system_template: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def tags_array(self) -> List[str]:
        """Convert tags string to array for frontend compatibility"""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    class Config:
        from_attributes = True


class TemplateVersionResponse(BaseModel):
    """Schema for template version history responses"""
    id: str
    template_id: str
    version_number: int
    change_summary: Optional[str]
    name: str
    subject: Optional[str]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TemplateLockRequest(BaseModel):
    """Schema for locking/unlocking templates"""
    action: str = Field(..., description="Action: 'lock' or 'unlock'")


class TemplateList(BaseModel):
    """Schema for paginated template list responses"""
    templates: List[TemplateResponse]
    total: int
    page: int
    limit: int
    pages: int


class TemplateStats(BaseModel):
    """Schema for template statistics"""
    total_templates: int
    published_templates: int
    draft_templates: int
    archived_templates: int
    system_templates: int
    folders: List[str]
    most_used_template: Optional[dict] = None
