"""
Premium Features API endpoints for SaaS dashboard
Includes A/B testing, email preview, campaign logs, auto-save, versioning, and template management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import logging
import json

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.models import Campaign, Template, EmailTracker, CampaignRecipient
from ...database.user_models import User
from ...auth.api_key_auth import get_user_from_api_key
from ...schemas.campaigns import CampaignResponse
from ...schemas.api_keys import MessageResponse
from pydantic import BaseModel

router = APIRouter(prefix="/premium", tags=["Premium Features"])
logger = logging.getLogger(__name__)

# Pydantic models for premium features
class ABTestCreate(BaseModel):
    campaign_id: str
    variant_a_name: str
    variant_b_name: str
    variant_a_subject: str
    variant_b_subject: str
    variant_a_content: str
    variant_b_content: str
    test_percentage: int = 20
    winner_criteria: str = "open_rate"  # open_rate, click_rate, conversion_rate

class ABTestResult(BaseModel):
    test_id: str
    campaign_id: str
    variant_a_name: str
    variant_b_name: str
    variant_a_metrics: Dict[str, Any]
    variant_b_metrics: Dict[str, Any]
    winner: Optional[str]
    confidence_level: Optional[float]
    status: str

class EmailPreviewRequest(BaseModel):
    subject: str
    html_content: str
    text_content: Optional[str] = None
    recipient_email: str = "preview@example.com"

class EmailPreviewResponse(BaseModel):
    preview_id: str
    subject: str
    html_preview: str
    text_preview: Optional[str]
    preview_url: str
    mobile_preview_url: str
    created_at: datetime

class CampaignLog(BaseModel):
    log_id: str
    campaign_id: str
    event_type: str  # sent, delivered, opened, clicked, bounced, complained
    recipient_email: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]]

class AutoSaveData(BaseModel):
    campaign_id: str
    auto_save_id: str
    draft_data: Dict[str, Any]
    last_saved: datetime
    version: int

class CampaignVersion(BaseModel):
    id: str  # Changed from version_id to match frontend
    campaign_id: str
    version_number: int
    changes_summary: Optional[str]
    created_at: datetime
    created_by: str  # Changed from modified_by to match frontend
    snapshot_data: Dict[str, Any]  # Nested data instead of individual fields

class TemplateAssignment(BaseModel):
    campaign_id: str
    template_ids: List[str]
    assignment_rules: Optional[Dict[str, Any]]

# A/B Testing Endpoints
@router.post("/ab-tests", response_model=Dict[str, str])
async def create_ab_test(
    ab_test_data: ABTestCreate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Create a new A/B test for a campaign"""
    try:
        # Verify user owns the campaign
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == ab_test_data.campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Create A/B test record (mock implementation)
        test_id = str(uuid.uuid4())
        
        # In a real implementation, you would store this in a dedicated AB_Test table
        test_data = {
            "test_id": test_id,
            "campaign_id": ab_test_data.campaign_id,
            "variant_a": {
                "name": ab_test_data.variant_a_name,
                "subject": ab_test_data.variant_a_subject,
                "content": ab_test_data.variant_a_content
            },
            "variant_b": {
                "name": ab_test_data.variant_b_name,
                "subject": ab_test_data.variant_b_subject,
                "content": ab_test_data.variant_b_content
            },
            "test_percentage": ab_test_data.test_percentage,
            "winner_criteria": ab_test_data.winner_criteria,
            "status": "running",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Store in campaign metadata for now
        if not campaign.metadata:
            campaign.metadata = {}
        campaign.metadata["ab_test"] = test_data
        db.commit()
        
        return {"test_id": test_id, "status": "created"}
        
    except Exception as e:
        logger.error(f"Error creating A/B test: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create A/B test")

@router.get("/ab-tests/{test_id}/results", response_model=ABTestResult)
async def get_ab_test_results(
    test_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get A/B test results"""
    try:
        # Find campaign with this A/B test
        campaign = db.query(Campaign).filter(
            and_(Campaign.user_id == current_user.id, Campaign.metadata.contains(f'"test_id": "{test_id}"'))
        ).first()
        
        if not campaign or not campaign.metadata or "ab_test" not in campaign.metadata:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        ab_test = campaign.metadata["ab_test"]
        
        # Mock results (in real implementation, calculate from email tracking data)
        return ABTestResult(
            test_id=test_id,
            campaign_id=campaign.id,
            variant_a_name=ab_test["variant_a"]["name"],
            variant_b_name=ab_test["variant_b"]["name"],
            variant_a_metrics={
                "sent": 500,
                "opened": 125,
                "clicked": 25,
                "open_rate": 0.25,
                "click_rate": 0.05
            },
            variant_b_metrics={
                "sent": 500,
                "opened": 155,
                "clicked": 35,
                "open_rate": 0.31,
                "click_rate": 0.07
            },
            winner="variant_b",
            confidence_level=0.85,
            status="completed"
        )
        
    except Exception as e:
        logger.error(f"Error getting A/B test results: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get A/B test results")

@router.post("/ab-tests/{test_id}/select-winner")
async def select_ab_test_winner(
    test_id: str,
    winner_variant: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Select winner of A/B test and apply to campaign"""
    try:
        # Find and update campaign with winner
        campaign = db.query(Campaign).filter(
            and_(Campaign.user_id == current_user.id, Campaign.metadata.contains(f'"test_id": "{test_id}"'))
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="A/B test not found")
        
        ab_test = campaign.metadata["ab_test"]
        ab_test["winner"] = winner_variant
        ab_test["status"] = "completed"
        
        # Apply winner variant to campaign
        if winner_variant == "variant_a":
            campaign.subject = ab_test["variant_a"]["subject"]
            campaign.html_content = ab_test["variant_a"]["content"]
        else:
            campaign.subject = ab_test["variant_b"]["subject"]
            campaign.html_content = ab_test["variant_b"]["content"]
        
        db.commit()
        
        return {"message": f"Winner {winner_variant} applied to campaign"}
        
    except Exception as e:
        logger.error(f"Error selecting A/B test winner: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to select winner")

# Email Preview Endpoints
@router.post("/email-preview", response_model=EmailPreviewResponse)
async def generate_email_preview(
    preview_data: EmailPreviewRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Generate email preview with desktop and mobile views"""
    try:
        preview_id = str(uuid.uuid4())
        
        # In a real implementation, you would render the email with a proper template engine
        html_preview = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{preview_data.subject}</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
            {preview_data.html_content}
        </body>
        </html>
        """
        
        return EmailPreviewResponse(
            preview_id=preview_id,
            subject=preview_data.subject,
            html_preview=html_preview,
            text_preview=preview_data.text_content,
            preview_url=f"/api/v1/premium/email-preview/{preview_id}",
            mobile_preview_url=f"/api/v1/premium/email-preview/{preview_id}?mobile=true",
            created_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error generating email preview: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate preview")

@router.get("/email-preview/{preview_id}")
async def get_email_preview(
    preview_id: str,
    mobile: bool = Query(False, description="Show mobile preview"),
    current_user: User = Depends(get_current_user_from_jwt)
):
    """Serve email preview (mock implementation)"""
    # In a real implementation, retrieve stored preview data
    return {"message": f"Email preview {preview_id} (mobile: {mobile})"}

# Campaign Logs Endpoints
@router.get("/campaigns/{campaign_id}/logs", response_model=List[CampaignLog])
async def get_campaign_logs(
    campaign_id: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get detailed campaign delivery logs"""
    try:
        # Verify user owns campaign
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get email tracking events for this campaign
        query = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id)
        
        if event_type:
            # Filter by event type if specified
            pass  # Would implement event type filtering
        
        trackers = query.order_by(desc(EmailTracker.created_at)).offset(offset).limit(limit).all()
        
        # Convert to log format
        logs = []
        for tracker in trackers:
            logs.append(CampaignLog(
                log_id=str(uuid.uuid4()),
                campaign_id=campaign_id,
                event_type="sent",  # Would determine actual event type
                recipient_email=tracker.recipient_email,
                timestamp=tracker.created_at,
                metadata={
                    "tracker_id": tracker.id,
                    "user_agent": getattr(tracker, 'user_agent', None),
                    "ip_address": getattr(tracker, 'ip_address', None)
                }
            ))
        
        return logs
        
    except Exception as e:
        logger.error(f"Error getting campaign logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get campaign logs")

# Auto-save Endpoints
@router.post("/campaigns/{campaign_id}/auto-save")
async def auto_save_campaign(
    campaign_id: str,
    draft_data: Dict[str, Any],
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Auto-save campaign draft"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Store auto-save data in campaign metadata
        if not campaign.metadata:
            campaign.metadata = {}
        
        auto_save_id = str(uuid.uuid4())
        campaign.metadata["auto_save"] = {
            "auto_save_id": auto_save_id,
            "draft_data": draft_data,
            "last_saved": datetime.utcnow().isoformat(),
            "version": campaign.metadata.get("auto_save", {}).get("version", 0) + 1
        }
        
        db.commit()
        
        return {"auto_save_id": auto_save_id, "message": "Draft saved successfully"}
        
    except Exception as e:
        logger.error(f"Error auto-saving campaign: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to auto-save campaign")

@router.get("/campaigns/{campaign_id}/auto-save", response_model=Optional[AutoSaveData])
async def get_auto_save_data(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get latest auto-save data for campaign"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign or not campaign.metadata or "auto_save" not in campaign.metadata:
            return None
        
        auto_save = campaign.metadata["auto_save"]
        
        return AutoSaveData(
            campaign_id=campaign_id,
            auto_save_id=auto_save["auto_save_id"],
            draft_data=auto_save["draft_data"],
            last_saved=datetime.fromisoformat(auto_save["last_saved"]),
            version=auto_save["version"]
        )
        
    except Exception as e:
        logger.error(f"Error getting auto-save data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get auto-save data")

# Campaign Versioning Endpoints
@router.post("/campaigns/{campaign_id}/clone")
async def clone_campaign(
    campaign_id: str,
    name: Optional[str] = None,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Clone a campaign"""
    try:
        original = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not original:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Create cloned campaign
        cloned = Campaign(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            name=name or f"{original.name} (Copy)",
            subject=original.subject,
            html_content=original.html_content,
            text_content=original.text_content,
            status="draft",
            metadata=original.metadata.copy() if original.metadata else {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(cloned)
        db.commit()
        
        return {"campaign_id": cloned.id, "message": "Campaign cloned successfully"}
        
    except Exception as e:
        logger.error(f"Error cloning campaign: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clone campaign")

@router.get("/campaigns/{campaign_id}/versions", response_model=List[CampaignVersion])
async def get_campaign_versions(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get campaign version history"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get actual version history from database
        from app.database.models import CampaignVersion as CampaignVersionModel
        version_records = db.query(CampaignVersionModel).filter(
            CampaignVersionModel.campaign_id == campaign_id
        ).order_by(CampaignVersionModel.version_number.desc()).all()
        
        # If no versions exist, create an initial version from current campaign
        if not version_records:
            # Create initial version from current campaign state
            recipients = db.query(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id
            ).all()
            recipient_ids = [r.contact_id for r in recipients]
            
            initial_version = CampaignVersionModel(
                campaign_id=campaign_id,
                user_id=current_user.id,
                version_number=1,
                name=campaign.name,
                subject=campaign.subject,
                description=campaign.description,
                email_html="",  # You might want to get this from template or stored content
                email_text="",
                recipient_list=",".join(recipient_ids) if recipient_ids else "",
                changes_summary="Initial campaign creation",
                modified_by=current_user.email
            )
            db.add(initial_version)
            db.commit()
            version_records = [initial_version]
        
        # Convert to response model
        versions = []
        for record in version_records:
            # Create snapshot data from individual fields
            snapshot_data = {
                "name": record.name,
                "subject": record.subject,
                "description": record.description,
                "email_html": record.email_html,
                "email_text": record.email_text,
                "recipient_list": record.recipient_list,
                "recipients_count": len(record.recipient_list.split(',')) if record.recipient_list else 0,
                "status": "archived"  # Version status
            }
            
            versions.append(CampaignVersion(
                id=record.id,  # Changed from version_id
                campaign_id=record.campaign_id,
                version_number=record.version_number,
                changes_summary=record.changes_summary,
                created_at=record.created_at,
                created_by=record.modified_by,  # Map modified_by to created_by
                snapshot_data=snapshot_data
            ))
        
        return versions
        
    except Exception as e:
        logger.error(f"Error getting campaign versions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get campaign versions")

@router.get("/campaigns/{campaign_id}/versions/{version_id}", response_model=CampaignVersion)
async def get_campaign_version(
    campaign_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get a specific campaign version"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        from app.database.models import CampaignVersion as CampaignVersionModel
        version_record = db.query(CampaignVersionModel).filter(
            and_(
                CampaignVersionModel.campaign_id == campaign_id,
                CampaignVersionModel.id == version_id
            )
        ).first()
        
        if not version_record:
            raise HTTPException(status_code=404, detail="Version not found")
        
        # Create snapshot data from individual fields
        snapshot_data = {
            "name": version_record.name,
            "subject": version_record.subject,
            "description": version_record.description,
            "email_html": version_record.email_html,
            "email_text": version_record.email_text,
            "recipient_list": version_record.recipient_list,
            "recipients_count": len(version_record.recipient_list.split(',')) if version_record.recipient_list else 0,
            "status": "archived"  # Version status
        }
        
        return CampaignVersion(
            id=version_record.id,  # Changed from version_id
            campaign_id=version_record.campaign_id,
            version_number=version_record.version_number,
            changes_summary=version_record.changes_summary,
            created_at=version_record.created_at,
            created_by=version_record.modified_by,  # Map modified_by to created_by
            snapshot_data=snapshot_data
        )
        
    except Exception as e:
        logger.error(f"Error getting campaign version: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get campaign version")


@router.post("/campaigns/{campaign_id}/restore-version/{version_id}")
async def restore_campaign_version(
    campaign_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Restore campaign to a previous version - creates a new version with restored content"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Prevent restoration of campaigns that are currently sending
        if campaign.status == "sending":
            raise HTTPException(status_code=400, detail="Cannot restore campaign while it's being sent")
        
        from app.database.models import CampaignVersion as CampaignVersionModel
        version_to_restore = db.query(CampaignVersionModel).filter(
            and_(
                CampaignVersionModel.campaign_id == campaign_id,
                CampaignVersionModel.id == version_id
            )
        ).first()
        
        if not version_to_restore:
            raise HTTPException(status_code=404, detail="Version not found")
        
        # Create a new version before restoration (backup current state)
        current_recipients = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign_id
        ).all()
        current_recipient_ids = [r.contact_id for r in current_recipients]
        
        # Get next version number
        latest_version = db.query(CampaignVersionModel).filter(
            CampaignVersionModel.campaign_id == campaign_id
        ).order_by(CampaignVersionModel.version_number.desc()).first()
        
        next_version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create backup of current state
        backup_version = CampaignVersionModel(
            campaign_id=campaign_id,
            user_id=current_user.id,
            version_number=next_version_number,
            name=campaign.name,
            subject=campaign.subject,
            description=campaign.description,
            email_html="",  # Current content - you might want to implement content storage
            email_text="",
            recipient_list=",".join(current_recipient_ids) if current_recipient_ids else "",
            changes_summary=f"Backup before restoring to version {version_to_restore.version_number}",
            modified_by=current_user.email
        )
        db.add(backup_version)
        
        # Restore campaign to previous version
        campaign.name = version_to_restore.name
        campaign.subject = version_to_restore.subject
        campaign.description = version_to_restore.description
        campaign.updated_at = datetime.utcnow()
        
        # Create new version for the restoration
        restore_version = CampaignVersionModel(
            campaign_id=campaign_id,
            user_id=current_user.id,
            version_number=next_version_number + 1,
            name=version_to_restore.name,
            subject=version_to_restore.subject,
            description=version_to_restore.description,
            email_html=version_to_restore.email_html,
            email_text=version_to_restore.email_text,
            recipient_list=version_to_restore.recipient_list,
            changes_summary=f"Restored from version {version_to_restore.version_number}",
            modified_by=current_user.email
        )
        db.add(restore_version)
        
        # Restore recipients if they were different
        if version_to_restore.recipient_list:
            # Delete current recipients
            db.query(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign_id
            ).delete()
            
            # Add restored recipients
            restored_recipient_ids = version_to_restore.recipient_list.split(",")
            for contact_id in restored_recipient_ids:
                if contact_id.strip():
                    new_recipient = CampaignRecipient(
                        campaign_id=campaign_id,
                        contact_id=contact_id.strip(),
                        user_id=current_user.id
                    )
                    db.add(new_recipient)
        
        db.commit()
        
        return {"message": f"Campaign restored to version {version_to_restore.version_number}", "new_version": restore_version.version_number}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error restoring campaign version: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to restore campaign version")


@router.post("/campaigns/{campaign_id}/rollback/{version_id}")
async def rollback_campaign(
    campaign_id: str,
    version_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Legacy endpoint - redirects to restore-version"""
    return await restore_campaign_version(campaign_id, version_id, current_user, db)

# Template Assignment Endpoints
@router.post("/campaigns/{campaign_id}/assign-templates")
async def assign_templates_to_campaign(
    campaign_id: str,
    assignment: TemplateAssignment,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Assign multiple templates to a campaign"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Verify user owns all templates
        templates = db.query(Template).filter(
            and_(Template.id.in_(assignment.template_ids), Template.user_id == current_user.id)
        ).all()
        
        if len(templates) != len(assignment.template_ids):
            raise HTTPException(status_code=400, detail="Some templates not found or not owned by user")
        
        # Store template assignments in campaign metadata
        if not campaign.metadata:
            campaign.metadata = {}
        
        campaign.metadata["template_assignments"] = {
            "template_ids": assignment.template_ids,
            "assignment_rules": assignment.assignment_rules,
            "assigned_at": datetime.utcnow().isoformat()
        }
        
        db.commit()
        
        return {"message": f"Assigned {len(assignment.template_ids)} templates to campaign"}
        
    except Exception as e:
        logger.error(f"Error assigning templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to assign templates")

@router.post("/campaigns/{campaign_id}/validate-templates")
async def validate_template_assignments(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Validate template assignments for a campaign"""
    try:
        campaign = db.query(Campaign).filter(
            and_(Campaign.id == campaign_id, Campaign.user_id == current_user.id)
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        validation_results = {
            "valid": True,
            "issues": [],
            "template_count": 0
        }
        
        if campaign.metadata and "template_assignments" in campaign.metadata:
            template_ids = campaign.metadata["template_assignments"]["template_ids"]
            templates = db.query(Template).filter(Template.id.in_(template_ids)).all()
            
            validation_results["template_count"] = len(templates)
            
            # Check for missing templates
            found_ids = [t.id for t in templates]
            missing_ids = set(template_ids) - set(found_ids)
            
            if missing_ids:
                validation_results["valid"] = False
                validation_results["issues"].append(f"Missing templates: {list(missing_ids)}")
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Error validating templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to validate templates")
