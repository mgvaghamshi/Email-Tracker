"""
Campaign Version Service
Automatically tracks campaign changes and creates version history
"""
from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import Optional

from ..database.models import Campaign, CampaignRecipient, CampaignVersion
from ..database.user_models import User

logger = logging.getLogger(__name__)


def create_campaign_version(
    db: Session,
    campaign: Campaign,
    user: User,
    changes_summary: str = "Campaign updated",
    email_html: Optional[str] = None,
    email_text: Optional[str] = None
) -> CampaignVersion:
    """
    Create a new version record for a campaign
    
    Args:
        db: Database session
        campaign: Campaign object
        user: User who made the changes
        changes_summary: Description of what changed
        email_html: HTML content of the email (optional)
        email_text: Text content of the email (optional)
    
    Returns:
        CampaignVersion: The created version record
    """
    try:
        # Get current recipients
        recipients = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign.id
        ).all()
        recipient_ids = [r.contact_id for r in recipients]
        
        # Get the next version number
        latest_version = db.query(CampaignVersion).filter(
            CampaignVersion.campaign_id == campaign.id
        ).order_by(CampaignVersion.version_number.desc()).first()
        
        next_version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create new version record
        version = CampaignVersion(
            campaign_id=campaign.id,
            user_id=user.id,
            version_number=next_version_number,
            name=campaign.name,
            subject=campaign.subject,
            description=campaign.description,
            email_html=email_html or "",
            email_text=email_text or "",
            recipient_list=",".join(recipient_ids) if recipient_ids else "",
            changes_summary=changes_summary,
            modified_by=user.email
        )
        
        db.add(version)
        db.commit()
        
        logger.info(f"Created version {next_version_number} for campaign {campaign.id}")
        return version
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating campaign version: {str(e)}")
        raise


def auto_version_campaign_update(
    db: Session,
    campaign_id: str,
    user: User,
    old_values: dict,
    new_values: dict
) -> Optional[CampaignVersion]:
    """
    Automatically create a version when campaign is updated
    
    Args:
        db: Database session
        campaign_id: ID of the campaign being updated
        user: User making the changes
        old_values: Dictionary of old field values
        new_values: Dictionary of new field values
    
    Returns:
        CampaignVersion: Created version or None if no significant changes
    """
    try:
        campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return None
        
        # Determine what changed
        changes = []
        significant_fields = ['name', 'subject', 'description']
        
        for field in significant_fields:
            if field in old_values and field in new_values:
                if old_values[field] != new_values[field]:
                    changes.append(f"{field} changed from '{old_values[field]}' to '{new_values[field]}'")
        
        # Only create version if there were significant changes
        if changes:
            changes_summary = "; ".join(changes)
            return create_campaign_version(
                db=db,
                campaign=campaign,
                user=user,
                changes_summary=changes_summary
            )
        
        return None
        
    except Exception as e:
        logger.error(f"Error in auto-versioning: {str(e)}")
        return None


def cleanup_old_versions(db: Session, campaign_id: str, keep_versions: int = 50):
    """
    Clean up old versions to prevent unlimited growth
    
    Args:
        db: Database session
        campaign_id: Campaign ID to clean up
        keep_versions: Number of versions to keep (default: 50)
    """
    try:
        # Get versions ordered by version number (newest first)
        versions = db.query(CampaignVersion).filter(
            CampaignVersion.campaign_id == campaign_id
        ).order_by(CampaignVersion.version_number.desc()).all()
        
        # If we have more than the limit, delete the oldest ones
        if len(versions) > keep_versions:
            versions_to_delete = versions[keep_versions:]
            for version in versions_to_delete:
                db.delete(version)
            
            db.commit()
            logger.info(f"Cleaned up {len(versions_to_delete)} old versions for campaign {campaign_id}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up old versions: {str(e)}")
