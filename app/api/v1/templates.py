"""
Template management endpoints with premium features
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, distinct
from typing import List, Optional
import uuid
import json
from datetime import datetime

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt, get_optional_user_from_jwt
from ...database.models import Template, TemplateVersion
from ...database.user_models import User
from ...schemas.templates import (
    TemplateCreate, TemplateUpdate, TemplateResponse, TemplateList, 
    TemplateStats, TemplateVersionResponse, TemplateLockRequest
)

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", summary="List all templates", response_model=TemplateList)
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
    current_user: Optional[User] = Depends(get_optional_user_from_jwt),
    db: Session = Depends(get_db)
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
    # Base query - handle authenticated and unauthenticated users
    if current_user and include_system:
        # Authenticated user requesting user templates + system templates
        query = db.query(Template).filter(
            or_(
                Template.user_id == current_user.id,
                Template.is_system_template == True
            )
        )
    elif current_user:
        # Authenticated user requesting only their templates
        query = db.query(Template).filter(Template.user_id == current_user.id)
    elif include_system:
        # Unauthenticated user requesting only system templates
        query = db.query(Template).filter(Template.is_system_template == True)
    else:
        # Unauthenticated user not requesting system templates - return empty
        query = db.query(Template).filter(False)  # Returns no results
    
    # Apply filters
    if type:
        query = query.filter(Template.type == type)
    
    if status:
        query = query.filter(Template.status == status)
        
    if folder:
        query = query.filter(Template.folder == folder)
    
    if tags:
        tag_list = [tag.strip() for tag in tags.split(',')]
        tag_conditions = []
        for tag in tag_list:
            tag_conditions.append(Template.tags.like(f"%{tag}%"))
        if tag_conditions:
            query = query.filter(or_(*tag_conditions))
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Template.name.ilike(search_term),
                Template.description.ilike(search_term),
                Template.tags.ilike(search_term)
            )
        )
    
    # Get total count before applying pagination
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(Template, sort_by, Template.updated_at)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Get paginated results
    templates = query.offset(skip).limit(limit).all()
    
    # Calculate pagination info
    pages = (total + limit - 1) // limit
    
    return TemplateList(
        templates=templates,
        total=total,
        page=(skip // limit) + 1,
        limit=limit,
        pages=pages
    )


@router.post("/", summary="Create a new template", response_model=TemplateResponse)
async def create_template(
    template_data: TemplateCreate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create a new template with premium features.
    
    Premium Features:
    - **tags**: Comma-separated tags for organization
    - **folder**: Template folder/category
    - Automatic version tracking
    """
    # Create new template for authenticated user
    template = Template(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=template_data.name,
        type=template_data.type,
        status=template_data.status,
        subject=template_data.subject,
        html_content=template_data.html_content,
        text_content=template_data.text_content,
        description=template_data.description,
        thumbnail_url=template_data.thumbnail_url,
        tags=template_data.tags,
        folder=template_data.folder,
        usage_count=0,
        version=1,
        is_locked=False,
        is_system_template=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    # Create initial version history entry
    initial_version = TemplateVersion(
        id=str(uuid.uuid4()),
        template_id=template.id,
        user_id=current_user.id,
        version_number=1,
        change_summary="Initial version",
        name=template.name,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        description=template.description,
        created_at=datetime.utcnow()
    )
    
    db.add(initial_version)
    db.commit()
    
    return template


@router.get("/stats", summary="Get template statistics", response_model=TemplateStats)
async def get_template_stats(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive template statistics including premium metrics.
    """
    # Get template statistics for authenticated user (including system templates)
    stats_query = db.query(
        func.count(Template.id).label('total'),
        func.sum(case((Template.status == 'published', 1), else_=0)).label('published'),
        func.sum(case((Template.status == 'draft', 1), else_=0)).label('draft'),
        func.sum(case((Template.status == 'archived', 1), else_=0)).label('archived'),
        func.sum(case((Template.is_system_template == True, 1), else_=0)).label('system')
    ).filter(
        or_(
            Template.user_id == current_user.id,
            Template.is_system_template == True
        )
    ).first()
    
    # Get distinct folders
    folders_query = db.query(distinct(Template.folder)).filter(
        and_(
            Template.user_id == current_user.id,
            Template.folder.isnot(None),
            Template.folder != ''
        )
    ).all()
    folders = [f[0] for f in folders_query if f[0]]
    
    # Get most used template for authenticated user
    most_used = db.query(Template).filter(
        Template.user_id == current_user.id
    ).order_by(Template.usage_count.desc()).first()
    
    most_used_dict = None
    if most_used:
        most_used_dict = {
            "id": most_used.id,
            "name": most_used.name,
            "usage_count": most_used.usage_count
        }
    
    return TemplateStats(
        total_templates=stats_query.total or 0,
        published_templates=stats_query.published or 0,
        draft_templates=stats_query.draft or 0,
        archived_templates=stats_query.archived or 0,
        system_templates=stats_query.system or 0,
        folders=folders,
        most_used_template=most_used_dict
    )


@router.get("/system", summary="Get system templates")
async def get_system_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    type: Optional[str] = Query(None, description="Filter by template type"),
    tags: Optional[str] = Query(None, description="Filter by tags"),
    is_premium: Optional[bool] = Query(None, description="Filter by premium status"),
    db: Session = Depends(get_db)
):
    """Get system templates (pre-built professional templates) - No authentication required."""
    # Query templates table for system templates
    query = db.query(Template).filter(Template.is_system_template == True)
    
    # Apply filters
    if type:
        query = query.filter(Template.type == type)
    
    system_templates = query.all()
    
    # Convert to response format
    templates = []
    for template in system_templates:
        # Parse tags from JSON string or comma-separated string
        tags_list = []
        if template.tags:
            try:
                if isinstance(template.tags, str):
                    # Try to parse as JSON first, then fall back to comma-separated
                    try:
                        tags_list = json.loads(template.tags)
                    except:
                        tags_list = [tag.strip() for tag in template.tags.split(',') if tag.strip()]
                else:
                    tags_list = template.tags or []
            except:
                tags_list = []
        
        template_dict = {
            "id": template.id,
            "name": template.name,
            "type": template.type,
            "description": template.description,
            "thumbnail_url": template.thumbnail_url,
            "html_content": template.html_content,
            "text_content": template.text_content,
            "tags": tags_list,
            "usage_count": template.usage_count or 0,
            "is_system_template": template.is_system_template,
            "last_used_at": template.last_used_at,
            "created_at": template.created_at,
            "updated_at": template.updated_at
        }
        
        # Apply additional filters
        if tags:
            tag_list = [tag.strip().lower() for tag in tags.split(",")]
            if not any(tag in [tg.lower() for tg in tags_list] for tag in tag_list):
                continue
        
        templates.append(template_dict)
    
    return templates


@router.get("/tags", summary="Get all template tags")
async def get_template_tags(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get all unique tags from user templates."""
    # Get all unique tags from user templates
    user_templates = db.query(Template).filter(Template.user_id == current_user.id).all()
    
    all_tags = set()
    for template in user_templates:
        if template.tags:
            tags = template.tags.split(',') if isinstance(template.tags, str) else []
            all_tags.update([tag.strip() for tag in tags if tag.strip()])
    
    # Add some common tags
    common_tags = ["marketing", "newsletter", "promotional", "welcome", "transactional", "seasonal", "urgent", "follow-up"]
    all_tags.update(common_tags)
    
    return sorted(list(all_tags))


@router.get("/folders", summary="Get all template folders")
async def get_template_folders(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get all template folders/categories for the user.
    """
    folders = db.query(distinct(Template.folder)).filter(
        and_(
            Template.user_id == current_user.id,
            Template.folder.isnot(None),
            Template.folder != ''
        )
    ).all()
    
    folder_list = [f[0] for f in folders if f[0]]
    
    # Add counts for each folder
    folder_stats = []
    for folder in folder_list:
        count = db.query(Template).filter(
            and_(
                Template.user_id == current_user.id,
                Template.folder == folder
            )
        ).count()
        folder_stats.append({"name": folder, "count": count})
    
    return {"folders": folder_stats}


@router.get("/{template_id}", summary="Get template by ID", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get a specific template by ID.
    """
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.put("/{template_id}", summary="Update template", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template_data: TemplateUpdate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Update an existing template with version history tracking.
    """
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Check if template is locked by another user
    if template.is_locked and template.locked_by != current_user.id:
        raise HTTPException(status_code=423, detail="Template is locked by another user")
    
    # Create version history entry before updating
    if any([template_data.name, template_data.subject, template_data.html_content, 
            template_data.text_content, template_data.description]):
        
        template.version += 1
        version_entry = TemplateVersion(
            id=str(uuid.uuid4()),
            template_id=template.id,
            user_id=current_user.id,
            version_number=template.version,
            change_summary=template_data.change_summary or "Template updated",
            name=template_data.name or template.name,
            subject=template_data.subject or template.subject,
            html_content=template_data.html_content or template.html_content,
            text_content=template_data.text_content or template.text_content,
            description=template_data.description or template.description,
            created_at=datetime.utcnow()
        )
        db.add(version_entry)
    
    # Update fields
    update_data = template_data.dict(exclude_unset=True, exclude={'change_summary'})
    for field, value in update_data.items():
        setattr(template, field, value)
    
    template.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(template)
    
    return template


@router.delete("/{template_id}", summary="Delete template")
async def delete_template(
    template_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Delete a template.
    """
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    return {"message": "Template deleted successfully"}


@router.post("/{template_id}/duplicate", summary="Duplicate template", response_model=TemplateResponse)
async def duplicate_template(
    template_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create a duplicate of an existing template.
    """
    # Get original template
    original_template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not original_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create duplicate with premium features
    duplicate = Template(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=f"{original_template.name} (Copy)",
        type=original_template.type,
        status="draft",  # Always create duplicates as draft
        subject=original_template.subject,
        html_content=original_template.html_content,
        text_content=original_template.text_content,
        description=original_template.description,
        thumbnail_url=original_template.thumbnail_url,
        tags=original_template.tags,
        folder=original_template.folder,
        usage_count=0,
        version=1,
        is_locked=False,
        is_system_template=False,
        parent_template_id=original_template.id,  # Link to original for A/B testing
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(duplicate)
    db.commit()
    db.refresh(duplicate)
    
    return duplicate


# Premium Feature Endpoints

@router.get("/{template_id}/versions", summary="Get template version history", response_model=List[TemplateVersionResponse])
async def get_template_versions(
    template_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get version history for a template.
    """
    # Verify template ownership
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    versions = db.query(TemplateVersion).filter(
        TemplateVersion.template_id == template_id
    ).order_by(TemplateVersion.version_number.desc()).all()
    
    return versions


@router.post("/{template_id}/lock", summary="Lock/unlock template for collaboration")
async def manage_template_lock(
    template_id: str,
    lock_request: TemplateLockRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Lock or unlock a template for collaborative editing.
    """
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if lock_request.action == "lock":
        if template.is_locked and template.locked_by != current_user.id:
            raise HTTPException(status_code=423, detail="Template is already locked by another user")
        
        template.is_locked = True
        template.locked_by = current_user.id
        template.locked_at = datetime.utcnow()
        message = "Template locked successfully"
        
    elif lock_request.action == "unlock":
        if template.is_locked and template.locked_by != current_user.id:
            raise HTTPException(status_code=403, detail="You can only unlock templates you have locked")
        
        template.is_locked = False
        template.locked_by = None
        template.locked_at = None
        message = "Template unlocked successfully"
        
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'lock' or 'unlock'")
    
    db.commit()
    
    return {"message": message, "is_locked": template.is_locked}


@router.get("/{template_id}/variations", summary="Get A/B template variations")
async def get_template_variations(
    template_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get all A/B variations of a template.
    """
    # Get the main template
    template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Get all variations (templates with this as parent)
    variations = db.query(Template).filter(
        and_(
            Template.parent_template_id == template_id,
            Template.user_id == current_user.id
        )
    ).all()
    
    return {
        "main_template": template,
        "variations": variations,
        "total_variations": len(variations)
    }


@router.post("/{template_id}/create-variation", summary="Create A/B variation", response_model=TemplateResponse)
async def create_template_variation(
    template_id: str,
    variation_name: str = Query(..., description="Name for the variation"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create an A/B test variation of an existing template.
    """
    # Get original template
    original_template = db.query(Template).filter(
        and_(
            Template.id == template_id,
            Template.user_id == current_user.id
        )
    ).first()
    
    if not original_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Create variation
    variation = Template(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=variation_name,
        type=original_template.type,
        status="draft",
        subject=original_template.subject,
        html_content=original_template.html_content,
        text_content=original_template.text_content,
        description=f"A/B variation of {original_template.name}",
        thumbnail_url=original_template.thumbnail_url,
        tags=original_template.tags,
        folder=original_template.folder,
        usage_count=0,
        version=1,
        is_locked=False,
        is_system_template=False,
        parent_template_id=template_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(variation)
    db.commit()
    db.refresh(variation)
    
    return variation


@router.post("/seed-system-templates", summary="Seed pre-built system templates")
async def seed_system_templates(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create pre-built system templates. (Admin only or first-time setup)
    """
    # Check if system templates already exist
    existing_count = db.query(Template).filter(Template.is_system_template == True).count()
    if existing_count > 0:
        return {"message": "System templates already exist", "count": existing_count}
    
    # Pre-built templates data
    system_templates = [
        {
            "name": "Welcome Email Template",
            "type": "welcome",
            "subject": "Welcome to {{company_name}}!",
            "description": "A warm welcome email for new subscribers",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
                    <h1 style="color: white; margin: 0;">Welcome to {{company_name}}!</h1>
                </div>
                <div style="padding: 30px;">
                    <h2>Hi {{user_name}},</h2>
                    <p>Thank you for joining our community! We're excited to have you on board.</p>
                    <p>Here's what you can expect:</p>
                    <ul>
                        <li>Regular updates about our products</li>
                        <li>Exclusive offers and discounts</li>
                        <li>Tips and tutorials</li>
                    </ul>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{cta_link}}" style="background: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">Get Started</a>
                    </div>
                    <p>Best regards,<br>The {{company_name}} Team</p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "welcome,onboarding,new-user"
        },
        {
            "name": "Weekly Newsletter",
            "type": "newsletter",
            "subject": "{{company_name}} Weekly Update - {{date}}",
            "description": "Weekly newsletter template with updates and news",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #f8f9fa; padding: 20px; text-align: center;">
                    <h1 style="color: #333;">Weekly Newsletter</h1>
                    <p style="color: #666;">{{date}}</p>
                </div>
                <div style="padding: 30px;">
                    <h2>This Week's Highlights</h2>
                    <div style="border-left: 4px solid #007bff; padding-left: 20px; margin: 20px 0;">
                        <h3>{{article_title_1}}</h3>
                        <p>{{article_summary_1}}</p>
                        <a href="{{article_link_1}}">Read more →</a>
                    </div>
                    <div style="border-left: 4px solid #28a745; padding-left: 20px; margin: 20px 0;">
                        <h3>{{article_title_2}}</h3>
                        <p>{{article_summary_2}}</p>
                        <a href="{{article_link_2}}">Read more →</a>
                    </div>
                    <hr style="margin: 30px 0;">
                    <p style="text-align: center; color: #666;">
                        <a href="{{unsubscribe_link}}">Unsubscribe</a> | 
                        <a href="{{preferences_link}}">Update Preferences</a>
                    </p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "newsletter,weekly,updates"
        },
        {
            "name": "Product Launch Promo",
            "type": "promotional",
            "subject": "🚀 Introducing {{product_name}} - Now Available!",
            "description": "Promotional email for product launches",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(45deg, #ff6b6b, #ee5a24); padding: 40px; text-align: center; color: white;">
                    <h1 style="margin: 0;">🚀 {{product_name}} is Here!</h1>
                    <p style="font-size: 18px; margin: 10px 0 0 0;">The wait is over</p>
                </div>
                <div style="padding: 30px;">
                    <h2>Meet {{product_name}}</h2>
                    <p>{{product_description}}</p>
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3>Key Features:</h3>
                        <ul>
                            <li>{{feature_1}}</li>
                            <li>{{feature_2}}</li>
                            <li>{{feature_3}}</li>
                        </ul>
                    </div>
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{cta_link}}" style="background: #ff6b6b; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 18px;">Get {{product_name}} Now</a>
                    </div>
                    <p style="text-align: center; color: #666;">
                        <strong>Special Launch Price: {{price}}</strong><br>
                        <small>Limited time offer</small>
                    </p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "promotional,launch,product,announcement"
        },
        {
            "name": "Event Invitation",
            "type": "transactional",
            "subject": "You're Invited: {{event_name}}",
            "description": "Professional event invitation template",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #2c3e50; padding: 40px; text-align: center; color: white;">
                    <h1 style="margin: 0;">You're Invited!</h1>
                    <h2 style="margin: 10px 0; color: #ecf0f1;">{{event_name}}</h2>
                </div>
                <div style="padding: 30px;">
                    <p>Dear {{attendee_name}},</p>
                    <p>We're excited to invite you to {{event_name}}.</p>
                    
                    <div style="background: #ecf0f1; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Event Details</h3>
                        <p><strong>📅 Date:</strong> {{event_date}}</p>
                        <p><strong>🕒 Time:</strong> {{event_time}}</p>
                        <p><strong>📍 Location:</strong> {{event_location}}</p>
                        <p><strong>👥 Expected Attendees:</strong> {{attendee_count}}</p>
                    </div>
                    
                    <h3>What to Expect:</h3>
                    <p>{{event_description}}</p>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{rsvp_link}}" style="background: #27ae60; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">RSVP Now</a>
                    </div>
                    
                    <p>We look forward to seeing you there!</p>
                    <p>Best regards,<br>{{organizer_name}}</p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "event,invitation,rsvp"
        },
        {
            "name": "Flash Sale Alert",
            "type": "promotional",
            "subject": "⚡ Flash Sale: {{discount}}% OFF Everything!",
            "description": "Urgent flash sale promotional email",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 40px; text-align: center; color: white;">
                    <h1 style="margin: 0; font-size: 36px;">⚡ FLASH SALE</h1>
                    <h2 style="margin: 10px 0; background: rgba(255,255,255,0.2); padding: 15px; border-radius: 5px;">{{discount}}% OFF EVERYTHING</h2>
                    <p style="font-size: 18px;">Limited Time Only!</p>
                </div>
                <div style="padding: 30px;">
                    <div style="text-align: center; background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                        <h3 style="margin: 0; color: #856404;">⏰ Hurry! Sale ends in:</h3>
                        <p style="font-size: 24px; font-weight: bold; color: #856404; margin: 10px 0;">{{countdown_timer}}</p>
                    </div>
                    
                    <h3>Featured Sale Items:</h3>
                    <div style="display: flex; margin: 20px 0;">
                        <div style="flex: 1; text-align: center; padding: 0 10px;">
                            <h4>{{item_1_name}}</h4>
                            <p style="text-decoration: line-through; color: #999;">{{item_1_original_price}}</p>
                            <p style="font-size: 20px; font-weight: bold; color: #f5576c;">{{item_1_sale_price}}</p>
                        </div>
                        <div style="flex: 1; text-align: center; padding: 0 10px;">
                            <h4>{{item_2_name}}</h4>
                            <p style="text-decoration: line-through; color: #999;">{{item_2_original_price}}</p>
                            <p style="font-size: 20px; font-weight: bold; color: #f5576c;">{{item_2_sale_price}}</p>
                        </div>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{shop_now_link}}" style="background: #f5576c; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-size: 20px; font-weight: bold;">SHOP NOW</a>
                    </div>
                    
                    <p style="text-align: center; color: #666; font-size: 12px;">
                        Use code: <strong>{{promo_code}}</strong> at checkout<br>
                        *Valid until {{expiry_date}}. Terms and conditions apply.
                    </p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "flash-sale,urgent,promotional,discount"
        },
        {
            "name": "Feedback Request",
            "type": "transactional",
            "subject": "We'd love your feedback on {{service_name}}",
            "description": "Customer feedback and review request email",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: #6c5ce7; padding: 40px; text-align: center; color: white;">
                    <h1 style="margin: 0;">Your Opinion Matters!</h1>
                    <p style="font-size: 18px; margin: 10px 0 0 0;">Help us improve {{service_name}}</p>
                </div>
                <div style="padding: 30px;">
                    <p>Hi {{customer_name}},</p>
                    <p>Thank you for using {{service_name}}! We hope you had a great experience.</p>
                    <p>Your feedback is incredibly valuable to us and helps us improve our service for everyone.</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <h3>How was your experience?</h3>
                        <div style="margin: 20px 0;">
                            <a href="{{rating_5_link}}" style="text-decoration: none; margin: 0 5px; font-size: 30px;">⭐</a>
                            <a href="{{rating_4_link}}" style="text-decoration: none; margin: 0 5px; font-size: 30px;">⭐</a>
                            <a href="{{rating_3_link}}" style="text-decoration: none; margin: 0 5px; font-size: 30px;">⭐</a>
                            <a href="{{rating_2_link}}" style="text-decoration: none; margin: 0 5px; font-size: 30px;">⭐</a>
                            <a href="{{rating_1_link}}" style="text-decoration: none; margin: 0 5px; font-size: 30px;">⭐</a>
                        </div>
                        <p style="color: #666; font-size: 14px;">Click the stars to rate your experience</p>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{detailed_feedback_link}}" style="background: #6c5ce7; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">Leave Detailed Feedback</a>
                    </div>
                    
                    <p>As a token of our appreciation, you'll receive a <strong>{{reward}}</strong> for completing our feedback survey.</p>
                    
                    <p>Thank you for taking the time to help us improve!</p>
                    <p>Best regards,<br>The {{company_name}} Team</p>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "feedback,review,survey,customer-service"
        },
        {
            "name": "Seasonal Greeting",
            "type": "newsletter",
            "subject": "{{season}} Greetings from {{company_name}}!",
            "description": "Seasonal holiday and greeting email template",
            "html_content": """
            <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center; color: white;">
                    <h1 style="margin: 0;">{{season}} Greetings!</h1>
                    <p style="font-size: 18px; margin: 10px 0 0 0;">From all of us at {{company_name}}</p>
                </div>
                <div style="padding: 30px;">
                    <p>Dear {{customer_name}},</p>
                    <p>As we celebrate {{holiday_name}}, we wanted to take a moment to express our gratitude for your continued support and loyalty.</p>
                    
                    <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                        <h3>{{seasonal_message_title}}</h3>
                        <p style="font-style: italic; color: #666;">{{seasonal_message}}</p>
                    </div>
                    
                    <h3>Special {{season}} Offers:</h3>
                    <ul>
                        <li>{{offer_1}}</li>
                        <li>{{offer_2}}</li>
                        <li>{{offer_3}}</li>
                    </ul>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="{{seasonal_offers_link}}" style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px;">View {{season}} Offers</a>
                    </div>
                    
                    <p>Wishing you and your loved ones a wonderful {{holiday_name}} filled with joy, peace, and happiness.</p>
                    
                    <p>Warm regards,<br>The {{company_name}} Team</p>
                    
                    <div style="text-align: center; margin: 30px 0; color: #666; font-size: 14px;">
                        <p>{{company_address}}<br>
                        {{company_phone}} | {{company_email}}</p>
                    </div>
                </div>
            </body>
            </html>
            """,
            "folder": "System Templates",
            "tags": "seasonal,holiday,greeting,celebration"
        }
    ]
    
    # Create system templates
    created_templates = []
    for template_data in system_templates:
        template = Template(
            id=str(uuid.uuid4()),
            user_id=None,  # System templates don't belong to specific users
            name=template_data["name"],
            type=template_data["type"],
            status="published",
            subject=template_data["subject"],
            html_content=template_data["html_content"],
            text_content=template_data.get("text_content"),
            description=template_data["description"],
            thumbnail_url=template_data.get("thumbnail_url"),
            tags=template_data["tags"],
            folder=template_data["folder"],
            usage_count=0,
            version=1,
            is_locked=False,
            is_system_template=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(template)
        created_templates.append(template_data["name"])
    
    db.commit()
    
    return {
        "message": "System templates created successfully",
        "templates": created_templates,
        "count": len(created_templates)
    }
