"""
Template Management API Endpoints
Handles all template-related operations including CRUD, versioning, and template statistics
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
import uuid
import logging

from ...db import SessionLocal
from ...models import EmailTemplate
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============= Pydantic Schemas =============

class TemplateCreate(BaseModel):
    """Schema for creating a new template"""
    name: str = Field(..., description="Template name")
    type: str = Field(..., description="Template type (newsletter, promotional, transactional, welcome)")
    status: str = Field(default="draft", description="Template status (draft, published, archived)")
    subject: Optional[str] = Field(None, description="Email subject line")
    html_content: Optional[str] = Field(None, description="HTML content of the template")
    text_content: Optional[str] = Field(None, description="Plain text content of the template")
    description: Optional[str] = Field(None, description="Template description")
    thumbnail_url: Optional[str] = Field(None, description="Template thumbnail URL")
    tags: Optional[str] = Field(None, description="Comma-separated tags")
    folder: Optional[str] = Field(None, description="Template folder/category")


class TemplateUpdate(BaseModel):
    """Schema for updating an existing template"""
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[str] = None
    folder: Optional[str] = None


class TemplateResponse(BaseModel):
    """Schema for template responses"""
    id: str
    user_id: str
    name: str
    type: str
    status: str = "draft"
    subject: Optional[str] = None
    html_content: Optional[str] = None
    text_content: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    tags: Optional[str] = None
    folder: Optional[str] = None
    usage_count: int = 0
    version: int = 1
    is_locked: bool = False
    locked_by: Optional[str] = None
    locked_at: Optional[datetime] = None
    parent_template_id: Optional[str] = None
    is_system_template: bool = False
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    tags_array: List[str] = Field(default_factory=list, description="Convert tags string to array")

    class Config:
        from_attributes = True


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
    draft_templates: int
    published_templates: int
    archived_templates: int
    total_usage: int
    most_used_template: Optional[Dict[str, Any]] = None


class TemplateLockRequest(BaseModel):
    """Schema for locking/unlocking templates"""
    action: str = Field(..., description="Action: 'lock' or 'unlock'")


# ============= Utility Functions =============

def _convert_template_to_response(template: EmailTemplate) -> TemplateResponse:
    """Convert EmailTemplate model to TemplateResponse"""
    tags_array = []
    if template.tags:
        tags_array = [tag.strip() for tag in template.tags.split(",") if tag.strip()]
    
    return TemplateResponse(
        id=template.id,
        user_id=getattr(template, 'user_id', ''),
        name=template.name,
        type=getattr(template, 'type', 'general'),
        status=getattr(template, 'status', 'draft'),
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        description=getattr(template, 'description', None),
        thumbnail_url=getattr(template, 'thumbnail_url', None),
        tags=getattr(template, 'tags', None),
        folder=getattr(template, 'folder', None),
        usage_count=getattr(template, 'usage_count', 0),
        version=getattr(template, 'version', 1),
        is_locked=getattr(template, 'is_locked', False),
        locked_by=getattr(template, 'locked_by', None),
        locked_at=getattr(template, 'locked_at', None),
        parent_template_id=getattr(template, 'parent_template_id', None),
        is_system_template=getattr(template, 'is_system_template', False),
        last_used_at=getattr(template, 'last_used_at', None),
        created_at=template.created_at,
        updated_at=template.updated_at,
        tags_array=tags_array
    )


# ============= API Endpoints =============

@router.get("/", response_model=TemplateList)
async def list_templates(
    skip: int = Query(0, ge=0, description="Number of templates to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of templates to return"),
    type: Optional[str] = Query(None, description="Filter by template type"),
    status: Optional[str] = Query(None, description="Filter by template status"),
    folder: Optional[str] = Query(None, description="Filter by template folder"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    search: Optional[str] = Query(None, description="Search by template name or description"),
    include_system: bool = Query(False, description="Include system templates"),
    sort_by: str = Query("updated_at", description="Sort by field: name, created_at, updated_at, usage_count"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a paginated list of templates with advanced filtering and sorting.
    
    Premium Features:
    - **folder**: Filter by template folder/category
    - **tags**: Filter by tags (comma-separated)
    - **include_system**: Include pre-built system templates
    - **sort_by**: Sort by various fields
    - **sort_order**: Ascending or descending order
    """
    try:
        # Base query - filter by active templates
        query = db.query(EmailTemplate).filter(EmailTemplate.is_active == True)
        
        # Apply type filter
        if type:
            query = query.filter(EmailTemplate.type == type) if hasattr(EmailTemplate, 'type') else query
        
        # Apply status filter
        if status:
            query = query.filter(EmailTemplate.status == status) if hasattr(EmailTemplate, 'status') else query
        
        # Apply folder filter
        if folder:
            query = query.filter(EmailTemplate.folder == folder) if hasattr(EmailTemplate, 'folder') else query
        
        # Apply tags filter
        if tags:
            # Filter templates that contain any of the specified tags
            tag_list = [tag.strip() for tag in tags.split(",")]
            if hasattr(EmailTemplate, 'tags'):
                tag_filters = [EmailTemplate.tags.contains(tag) for tag in tag_list]
                query = query.filter(or_(*tag_filters))
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            filters = [EmailTemplate.name.ilike(search_pattern)]
            if hasattr(EmailTemplate, 'description'):
                filters.append(EmailTemplate.description.ilike(search_pattern))
            query = query.filter(or_(*filters))
        
        # System templates filter
        if not include_system and hasattr(EmailTemplate, 'is_system_template'):
            query = query.filter(EmailTemplate.is_system_template == False)
        
        # Count total results before pagination
        total = query.count()
        
        # Apply sorting
        if sort_order.lower() == "desc":
            if sort_by == "name":
                query = query.order_by(desc(EmailTemplate.name))
            elif sort_by == "created_at":
                query = query.order_by(desc(EmailTemplate.created_at))
            elif sort_by == "usage_count" and hasattr(EmailTemplate, 'usage_count'):
                query = query.order_by(desc(EmailTemplate.usage_count))
            else:
                query = query.order_by(desc(EmailTemplate.updated_at))
        else:
            if sort_by == "name":
                query = query.order_by(EmailTemplate.name)
            elif sort_by == "created_at":
                query = query.order_by(EmailTemplate.created_at)
            elif sort_by == "usage_count" and hasattr(EmailTemplate, 'usage_count'):
                query = query.order_by(EmailTemplate.usage_count)
            else:
                query = query.order_by(EmailTemplate.updated_at)
        
        # Apply pagination
        templates = query.offset(skip).limit(limit).all()
        
        # Calculate pagination info
        page = (skip // limit) + 1
        pages = (total + limit - 1) // limit
        
        # Convert to response models
        template_responses = [_convert_template_to_response(template) for template in templates]
        
        return TemplateList(
            templates=template_responses,
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Error listing templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing templates: {str(e)}"
        )


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new template with premium features.
    
    Premium Features:
    - **tags**: Comma-separated tags for organization
    - **folder**: Template folder/category
    - Automatic version tracking
    """
    try:
        # Create new template
        new_template = EmailTemplate(
            id=str(uuid.uuid4()),
            name=template_data.name,
            subject=template_data.subject,
            html_content=template_data.html_content,
            text_content=template_data.text_content,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Add optional fields if they exist in the model
        if hasattr(EmailTemplate, 'user_id'):
            new_template.user_id = current_user.id
        if hasattr(EmailTemplate, 'type'):
            new_template.type = template_data.type
        if hasattr(EmailTemplate, 'status'):
            new_template.status = template_data.status
        if hasattr(EmailTemplate, 'description'):
            new_template.description = template_data.description
        if hasattr(EmailTemplate, 'thumbnail_url'):
            new_template.thumbnail_url = template_data.thumbnail_url
        if hasattr(EmailTemplate, 'tags'):
            new_template.tags = template_data.tags
        if hasattr(EmailTemplate, 'folder'):
            new_template.folder = template_data.folder
        if hasattr(EmailTemplate, 'usage_count'):
            new_template.usage_count = 0
        if hasattr(EmailTemplate, 'version'):
            new_template.version = 1
        if hasattr(EmailTemplate, 'is_locked'):
            new_template.is_locked = False
        if hasattr(EmailTemplate, 'is_system_template'):
            new_template.is_system_template = False
        
        db.add(new_template)
        db.commit()
        db.refresh(new_template)
        
        return _convert_template_to_response(new_template)
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating template: {str(e)}"
        )


@router.get("/stats", response_model=TemplateStats)
async def get_template_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive template statistics including premium metrics.
    """
    try:
        # Get total templates
        total_templates = db.query(EmailTemplate).filter(
            EmailTemplate.is_active == True
        ).count()
        
        # Get counts by status if available
        draft_count = 0
        published_count = 0
        archived_count = 0
        
        if hasattr(EmailTemplate, 'status'):
            draft_count = db.query(EmailTemplate).filter(
                EmailTemplate.is_active == True,
                EmailTemplate.status == 'draft'
            ).count()
            
            published_count = db.query(EmailTemplate).filter(
                EmailTemplate.is_active == True,
                EmailTemplate.status == 'published'
            ).count()
            
            archived_count = db.query(EmailTemplate).filter(
                EmailTemplate.is_active == True,
                EmailTemplate.status == 'archived'
            ).count()
        
        # Get total usage
        total_usage = 0
        if hasattr(EmailTemplate, 'usage_count'):
            result = db.query(func.sum(EmailTemplate.usage_count)).filter(
                EmailTemplate.is_active == True
            ).scalar()
            total_usage = result or 0
        
        # Get most used template
        most_used = None
        if hasattr(EmailTemplate, 'usage_count'):
            most_used_template = db.query(EmailTemplate).filter(
                EmailTemplate.is_active == True
            ).order_by(desc(EmailTemplate.usage_count)).first()
            
            if most_used_template:
                most_used = {
                    "id": most_used_template.id,
                    "name": most_used_template.name,
                    "usage_count": getattr(most_used_template, 'usage_count', 0)
                }
        
        return TemplateStats(
            total_templates=total_templates,
            draft_templates=draft_count,
            published_templates=published_count,
            archived_templates=archived_count,
            total_usage=total_usage,
            most_used_template=most_used
        )
        
    except Exception as e:
        logger.error(f"Error getting template stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template stats: {str(e)}"
        )


@router.get("/system")
async def get_system_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    type: Optional[str] = Query(None, description="Filter by template type"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    is_premium: Optional[bool] = Query(None, description="Filter by premium status"),
    db: Session = Depends(get_db)
):
    """
    Get system templates (pre-built professional templates) - No authentication required.
    """
    try:
        query = db.query(EmailTemplate).filter(EmailTemplate.is_active == True)
        
        if hasattr(EmailTemplate, 'is_system_template'):
            query = query.filter(EmailTemplate.is_system_template == True)
        
        if type and hasattr(EmailTemplate, 'type'):
            query = query.filter(EmailTemplate.type == type)
        
        if tags and hasattr(EmailTemplate, 'tags'):
            tag_list = [tag.strip() for tag in tags.split(",")]
            tag_filters = [EmailTemplate.tags.contains(tag) for tag in tag_list]
            query = query.filter(or_(*tag_filters))
        
        templates = query.all()
        
        return {
            "templates": [_convert_template_to_response(t) for t in templates],
            "total": len(templates)
        }
        
    except Exception as e:
        logger.error(f"Error getting system templates: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting system templates: {str(e)}"
        )


@router.get("/tags")
async def get_template_tags(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all unique tags from user templates.
    """
    try:
        if not hasattr(EmailTemplate, 'tags'):
            return {"tags": []}
        
        templates = db.query(EmailTemplate).filter(
            EmailTemplate.is_active == True
        ).all()
        
        # Extract all unique tags
        all_tags = set()
        for template in templates:
            if template.tags:
                tags = [tag.strip() for tag in template.tags.split(",") if tag.strip()]
                all_tags.update(tags)
        
        return {"tags": sorted(list(all_tags))}
        
    except Exception as e:
        logger.error(f"Error getting template tags: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template tags: {str(e)}"
        )


@router.get("/folders")
async def get_template_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all template folders/categories for the user.
    """
    try:
        if not hasattr(EmailTemplate, 'folder'):
            return {"folders": []}
        
        templates = db.query(EmailTemplate).filter(
            EmailTemplate.is_active == True
        ).all()
        
        # Extract all unique folders
        folders = set()
        for template in templates:
            if hasattr(template, 'folder') and template.folder:
                folders.add(template.folder)
        
        return {"folders": sorted(list(folders))}
        
    except Exception as e:
        logger.error(f"Error getting template folders: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template folders: {str(e)}"
        )


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific template by ID.
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        return _convert_template_to_response(template)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template: {str(e)}"
        )


@router.put("/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update template.
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Update fields
        update_data = template_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(template, field):
                setattr(template, field, value)
        
        template.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(template)
        
        return _convert_template_to_response(template)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating template: {str(e)}"
        )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete template (soft delete).
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Soft delete
        template.is_active = False
        template.updated_at = datetime.utcnow()
        
        db.commit()
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting template: {str(e)}"
        )


@router.post("/{template_id}/duplicate", response_model=TemplateResponse)
async def duplicate_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Duplicate an existing template.
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Create duplicate
        duplicate = EmailTemplate(
            id=str(uuid.uuid4()),
            name=f"{template.name} (Copy)",
            subject=template.subject,
            html_content=template.html_content,
            text_content=template.text_content,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Copy additional fields if they exist
        for field in ['user_id', 'type', 'status', 'description', 'thumbnail_url', 'tags', 'folder']:
            if hasattr(template, field):
                setattr(duplicate, field, getattr(template, field))
        
        if hasattr(duplicate, 'parent_template_id'):
            duplicate.parent_template_id = template_id
        
        db.add(duplicate)
        db.commit()
        db.refresh(duplicate)
        
        return _convert_template_to_response(duplicate)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error duplicating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error duplicating template: {str(e)}"
        )


@router.get("/{template_id}/versions")
async def get_template_versions(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all versions of a template.
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Return current version info
        return {
            "template_id": template_id,
            "current_version": getattr(template, 'version', 1),
            "versions": []  # Could be expanded with version history table
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting template versions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template versions: {str(e)}"
        )


@router.post("/{template_id}/lock")
async def lock_unlock_template(
    template_id: str,
    lock_request: TemplateLockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lock or unlock a template to prevent editing.
    """
    try:
        template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        if lock_request.action == "lock":
            if hasattr(template, 'is_locked'):
                template.is_locked = True
            if hasattr(template, 'locked_by'):
                template.locked_by = current_user.id
            if hasattr(template, 'locked_at'):
                template.locked_at = datetime.utcnow()
        elif lock_request.action == "unlock":
            if hasattr(template, 'is_locked'):
                template.is_locked = False
            if hasattr(template, 'locked_by'):
                template.locked_by = None
            if hasattr(template, 'locked_at'):
                template.locked_at = None
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Action must be 'lock' or 'unlock'"
            )
        
        template.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": f"Template {lock_request.action}ed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error locking/unlocking template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error locking/unlocking template: {str(e)}"
        )


@router.get("/{template_id}/variations")
async def get_template_variations(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all variations/copies of a template.
    """
    try:
        # Get templates that have this template as parent
        variations = []
        if hasattr(EmailTemplate, 'parent_template_id'):
            variations = db.query(EmailTemplate).filter(
                EmailTemplate.parent_template_id == template_id,
                EmailTemplate.is_active == True
            ).all()
        
        return {
            "template_id": template_id,
            "variations": [_convert_template_to_response(v) for v in variations],
            "total": len(variations)
        }
        
    except Exception as e:
        logger.error(f"Error getting template variations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting template variations: {str(e)}"
        )


@router.post("/{template_id}/create-variation", response_model=TemplateResponse)
async def create_template_variation(
    template_id: str,
    variation_data: TemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a variation of an existing template.
    """
    try:
        parent_template = db.query(EmailTemplate).filter(
            EmailTemplate.id == template_id,
            EmailTemplate.is_active == True
        ).first()
        
        if not parent_template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Parent template not found"
            )
        
        # Create variation
        variation = EmailTemplate(
            id=str(uuid.uuid4()),
            name=variation_data.name,
            subject=variation_data.subject,
            html_content=variation_data.html_content,
            text_content=variation_data.text_content,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        
        # Set parent template
        if hasattr(variation, 'parent_template_id'):
            variation.parent_template_id = template_id
        
        # Add other fields from request
        for field in ['user_id', 'type', 'status', 'description', 'thumbnail_url', 'tags', 'folder']:
            if hasattr(EmailTemplate, field):
                setattr(variation, field, getattr(variation_data, field, getattr(parent_template, field, None)))
        
        if hasattr(variation, 'user_id'):
            variation.user_id = current_user.id
        
        db.add(variation)
        db.commit()
        db.refresh(variation)
        
        return _convert_template_to_response(variation)
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating template variation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating template variation: {str(e)}"
        )
