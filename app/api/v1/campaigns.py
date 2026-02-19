"""
Campaign Management API Endpoints
Handles all campaign-related operations including CRUD, sending, scheduling, and analytics
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import logging
import os

from ...db import SessionLocal
from ...models import EmailCampaign, EmailTracker, EmailEvent
from ...email_schemas import (
    EmailCampaignCreate,
    EmailCampaignResponse,
    EmailCampaignWithStats,
    CampaignUpdate,
    EmailSendRequest,
    EmailSendResponse,
    EmailTrackerResponse
)
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User
from ...email_service import EmailService

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

# Initialize email service
email_service = EmailService()


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=List[EmailCampaignWithStats])
async def list_campaigns(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search campaigns by name or description"),
    status: Optional[str] = Query(None, description="Filter by status (active, completed, scheduled)"),
    sort_by: str = Query("created_at", description="Sort field (created_at, name, total_sent)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all campaigns with pagination, filtering, and statistics
    
    Returns detailed statistics for each campaign including:
    - Total emails sent, opened, clicked
    - Open rate, click rate, bounce rate
    - Recent activity (last 7 days)
    """
    try:
        # Base query
        query = db.query(EmailCampaign).filter(EmailCampaign.is_active == True)
        
        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                (EmailCampaign.name.ilike(search_pattern)) |
                (EmailCampaign.description.ilike(search_pattern))
            )
        
        # Apply sorting
        if sort_order.lower() == "desc":
            if sort_by == "name":
                query = query.order_by(desc(EmailCampaign.name))
            else:
                query = query.order_by(desc(EmailCampaign.created_at))
        else:
            if sort_by == "name":
                query = query.order_by(EmailCampaign.name)
            else:
                query = query.order_by(EmailCampaign.created_at)
        
        # Apply pagination
        campaigns = query.offset(skip).limit(limit).all()
        
        # Calculate stats for each campaign
        result = []
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        
        for campaign in campaigns:
            # Get all trackers for this campaign
            trackers = db.query(EmailTracker).filter(
                EmailTracker.campaign_id == campaign.id
            ).all()
            
            # Get recent trackers
            recent_trackers = db.query(EmailTracker).filter(
                EmailTracker.campaign_id == campaign.id,
                EmailTracker.created_at >= seven_days_ago
            ).all()
            
            # Calculate statistics
            total_sent = len(trackers)
            total_opens = sum(1 for t in trackers if t.opened_at)
            total_clicks = sum(t.click_count for t in trackers)
            
            # Count bounces
            total_bounces = db.query(func.count(EmailTracker.id)).filter(
                EmailTracker.campaign_id == campaign.id,
                EmailTracker.delivery_status == "bounced"
            ).scalar() or 0
            
            # Recent activity
            recent_opens = sum(1 for t in recent_trackers if t.opened_at)
            recent_clicks = sum(t.click_count for t in recent_trackers)
            
            # Last sent email
            last_sent = db.query(EmailTracker.sent_at).filter(
                EmailTracker.campaign_id == campaign.id,
                EmailTracker.sent_at.isnot(None)
            ).order_by(desc(EmailTracker.sent_at)).first()
            
            # Calculate rates
            open_rate = round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2)
            click_rate = round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2)
            bounce_rate = round((total_bounces / total_sent * 100) if total_sent > 0 else 0, 2)
            
            campaign_dict = {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "created_at": campaign.created_at,
                "total_sent": total_sent,
                "total_opens": total_opens,
                "total_clicks": total_clicks,
                "total_bounces": total_bounces,
                "open_rate": open_rate,
                "click_rate": click_rate,
                "bounce_rate": bounce_rate,
                "last_email_sent": last_sent[0] if last_sent else None,
                "recent_opens": recent_opens,
                "recent_clicks": recent_clicks
            }
            
            result.append(campaign_dict)
        
        return result
        
    except Exception as e:
        logger.error(f"Error listing campaigns: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list campaigns: {str(e)}")


@router.post("/", response_model=EmailCampaignResponse)
async def create_campaign(
    campaign: EmailCampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new email campaign
    
    A campaign groups related emails together for tracking and analytics purposes.
    """
    try:
        db_campaign = EmailCampaign(
            id=str(uuid.uuid4()),
            name=campaign.name,
            description=campaign.description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            is_active=True
        )
        db.add(db_campaign)
        db.commit()
        db.refresh(db_campaign)
        
        logger.info(f"Created campaign: {db_campaign.id} by user: {current_user.id}")
        
        return db_campaign
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create campaign: {str(e)}")


@router.get("/{campaign_id}", response_model=EmailCampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific campaign including statistics
    """
    try:
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get trackers for this campaign
        trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).all()
        
        # Calculate stats
        total_sent = len(trackers)
        total_opens = sum(1 for t in trackers if t.opened_at)
        total_clicks = sum(t.click_count for t in trackers)
        
        # Find last sent email
        last_sent = None
        for tracker in trackers:
            if tracker.sent_at:
                if not last_sent or tracker.sent_at > last_sent:
                    last_sent = tracker.sent_at
        
        # Build response with statistics
        campaign_dict = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "created_at": campaign.created_at,
            "updated_at": campaign.updated_at,
            "total_sent": total_sent,
            "total_opens": total_opens,
            "total_clicks": total_clicks,
            "open_rate": round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2),
            "click_rate": round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2),
            "last_email_sent": last_sent
        }
        
        return campaign_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaign: {str(e)}")


@router.put("/{campaign_id}", response_model=EmailCampaignResponse)
async def update_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing campaign
    
    Can update name and description. Statistics are read-only.
    """
    try:
        # Find the campaign
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Update only provided fields
        if campaign_update.name is not None:
            campaign.name = campaign_update.name
        if campaign_update.description is not None:
            campaign.description = campaign_update.description
        
        # Always update the timestamp
        campaign.updated_at = datetime.utcnow()
        
        # Save changes
        db.commit()
        db.refresh(campaign)
        
        logger.info(f"Updated campaign: {campaign_id} by user: {current_user.id}")
        
        return campaign
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update campaign: {str(e)}")


@router.delete("/{campaign_id}")
async def delete_campaign(
    campaign_id: str,
    hard_delete: bool = Query(False, description="Permanently delete instead of soft delete"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a campaign (soft delete by default)
    
    Soft delete marks the campaign as inactive but preserves all data.
    Hard delete permanently removes the campaign and all associated trackers.
    """
    try:
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        if hard_delete:
            # Hard delete - remove campaign and all trackers
            db.query(EmailTracker).filter(
                EmailTracker.campaign_id == campaign_id
            ).delete()
            db.delete(campaign)
            logger.info(f"Hard deleted campaign: {campaign_id} by user: {current_user.id}")
            message = "Campaign permanently deleted"
        else:
            # Soft delete - just mark as inactive
            campaign.is_active = False
            campaign.updated_at = datetime.utcnow()
            logger.info(f"Soft deleted campaign: {campaign_id} by user: {current_user.id}")
            message = "Campaign deactivated"
        
        db.commit()
        
        return {"success": True, "message": message, "campaign_id": campaign_id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting campaign {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete campaign: {str(e)}")


@router.get("/{campaign_id}/preview")
async def get_campaign_preview(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a preview of the campaign including sample emails and statistics
    """
    try:
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get sample trackers (first 5)
        sample_trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).limit(5).all()
        
        # Get all trackers for stats
        all_trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).all()
        
        # Calculate statistics
        total_sent = len(all_trackers)
        total_opens = sum(1 for t in all_trackers if t.opened_at)
        total_clicks = sum(t.click_count for t in all_trackers)
        
        preview_data = {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "created_at": campaign.created_at
            },
            "statistics": {
                "total_sent": total_sent,
                "total_opens": total_opens,
                "total_clicks": total_clicks,
                "open_rate": round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2),
                "click_rate": round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2)
            },
            "sample_emails": [
                {
                    "id": t.id,
                    "recipient": t.recipient_email,
                    "subject": t.subject,
                    "sent_at": t.sent_at,
                    "opened": t.opened_at is not None,
                    "click_count": t.click_count
                }
                for t in sample_trackers
            ]
        }
        
        return preview_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign preview {campaign_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaign preview: {str(e)}")


@router.post("/{campaign_id}/send", response_model=EmailSendResponse)
async def send_campaign(
    campaign_id: str,
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send an email as part of a campaign
    
    Creates a tracker and queues the email for sending in the background.
    """
    try:
        # Verify campaign exists
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Override campaign_id in request
        email_request.campaign_id = campaign_id
        
        # Create email tracker
        tracker_id = str(uuid.uuid4())
        tracking_pixel_url = f"{os.getenv('BASE_URL')}/track/open/{tracker_id}"
        
        # Use company name from environment if not provided
        if not email_request.from_name:
            email_request.from_name = os.getenv('SENDER_NAME', 'Cold Edge AI')
        
        # Create tracker record
        db_tracker = EmailTracker(
            id=tracker_id,
            campaign_id=campaign_id,
            name=email_request.to_name,
            company=email_request.company,
            position=email_request.position,
            email=email_request.to_email,
            subject=email_request.subject,
            body=email_request.html_content or email_request.text_content,
            delivered=False,
            recipient_email=email_request.to_email,
            sender_email=email_request.from_email,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            delivery_status="queued"
        )
        db.add(db_tracker)
        db.commit()
        
        # Send email in background
        async def send_and_update():
            success = await email_service.send_email(
                email_request,
                tracker_id,
                tracking_pixel_url
            )
            if success:
                db_tracker.delivered = True
                db_tracker.sent_at = datetime.utcnow()
                db_tracker.delivery_status = "sent"
            else:
                db_tracker.delivery_status = "failed"
            db.commit()
        
        background_tasks.add_task(send_and_update)
        
        logger.info(f"Queued email for campaign {campaign_id} to {email_request.to_email}")
        
        return EmailSendResponse(
            success=True,
            message=f"Email queued successfully for {email_request.to_email}",
            tracker_id=tracker_id,
            status="queued",
            campaign_id=campaign_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error sending campaign email: {str(e)}")
        return EmailSendResponse(
            success=False,
            message="Failed to send email",
            error=str(e)
        )


@router.post("/{campaign_id}/schedule")
async def schedule_campaign(
    campaign_id: str,
    scheduled_time: datetime,
    email_requests: List[EmailSendRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Schedule a campaign to be sent at a specific time
    
    Note: This creates scheduled records but requires a separate scheduler service to process them.
    """
    try:
        # Verify campaign exists
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Validate scheduled time is in the future
        if scheduled_time <= datetime.utcnow():
            raise HTTPException(
                status_code=400,
                detail="Scheduled time must be in the future"
            )
        
        # Create tracker records for all emails with scheduled status
        scheduled_trackers = []
        for email_request in email_requests:
            tracker_id = str(uuid.uuid4())
            
            db_tracker = EmailTracker(
                id=tracker_id,
                campaign_id=campaign_id,
                name=email_request.to_name,
                company=email_request.company,
                position=email_request.position,
                email=email_request.to_email,
                subject=email_request.subject,
                body=email_request.html_content or email_request.text_content,
                delivered=False,
                recipient_email=email_request.to_email,
                sender_email=email_request.from_email,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                sent_at=scheduled_time,  # Store scheduled time
                delivery_status="scheduled"
            )
            db.add(db_tracker)
            scheduled_trackers.append(tracker_id)
        
        db.commit()
        
        logger.info(f"Scheduled {len(scheduled_trackers)} emails for campaign {campaign_id} at {scheduled_time}")
        
        return {
            "success": True,
            "message": f"Scheduled {len(scheduled_trackers)} emails for {scheduled_time}",
            "campaign_id": campaign_id,
            "scheduled_time": scheduled_time,
            "scheduled_count": len(scheduled_trackers),
            "tracker_ids": scheduled_trackers
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error scheduling campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule campaign: {str(e)}")


@router.get("/{campaign_id}/logs", response_model=List[EmailTrackerResponse])
async def get_campaign_logs(
    campaign_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[str] = Query(None, description="Filter by status (sent, failed, bounced, opened)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get delivery logs for a campaign
    
    Returns all email trackers for the campaign with detailed delivery information.
    """
    try:
        # Verify campaign exists
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Build query
        query = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        )
        
        # Apply status filter
        if status:
            if status == "opened":
                query = query.filter(EmailTracker.opened_at.isnot(None))
            else:
                query = query.filter(EmailTracker.delivery_status == status)
        
        # Order by most recent first
        query = query.order_by(desc(EmailTracker.created_at))
        
        # Apply pagination
        trackers = query.offset(skip).limit(limit).all()
        
        # Format response
        result = []
        for tracker in trackers:
            result.append({
                "id": tracker.id,
                "campaign_id": tracker.campaign_id,
                "recipient_email": tracker.recipient_email,
                "sender_email": tracker.sender_email,
                "subject": tracker.subject,
                "sent_at": tracker.sent_at,
                "opened_at": tracker.opened_at,
                "open_count": tracker.open_count,
                "click_count": tracker.click_count,
                "delivery_status": tracker.delivery_status or "unknown",
                "created_at": tracker.created_at,
                "updated_at": tracker.updated_at
            })
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get campaign logs: {str(e)}")


@router.get("/{campaign_id}/auto-save")
async def get_auto_save(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get auto-saved data for a campaign
    
    Returns the campaign configuration and any unsent/draft emails.
    """
    try:
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Get draft trackers (not sent yet)
        draft_trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id,
            EmailTracker.sent_at.is_(None),
            EmailTracker.delivery_status.in_(["draft", "queued"])
        ).all()
        
        auto_save_data = {
            "campaign": {
                "id": campaign.id,
                "name": campaign.name,
                "description": campaign.description,
                "created_at": campaign.created_at,
                "updated_at": campaign.updated_at
            },
            "draft_emails": [
                {
                    "id": t.id,
                    "recipient_email": t.recipient_email,
                    "subject": t.subject,
                    "body": t.body,
                    "name": t.name,
                    "company": t.company,
                    "position": t.position,
                    "created_at": t.created_at
                }
                for t in draft_trackers
            ],
            "draft_count": len(draft_trackers)
        }
        
        return auto_save_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting auto-save data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get auto-save data: {str(e)}")


@router.post("/{campaign_id}/auto-save")
async def auto_save_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    draft_emails: Optional[List[EmailSendRequest]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Auto-save campaign data
    
    Saves campaign configuration and any draft emails without sending them.
    """
    try:
        # Find or create campaign
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            # Create new campaign for auto-save
            campaign = EmailCampaign(
                id=campaign_id,
                name=campaign_update.name or f"Campaign {campaign_id[:8]}",
                description=campaign_update.description or "Auto-saved campaign",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                is_active=True
            )
            db.add(campaign)
        else:
            # Update existing campaign
            if campaign_update.name:
                campaign.name = campaign_update.name
            if campaign_update.description:
                campaign.description = campaign_update.description
            campaign.updated_at = datetime.utcnow()
        
        # Save draft emails if provided
        saved_drafts = []
        if draft_emails:
            for email_request in draft_emails:
                tracker_id = str(uuid.uuid4())
                
                db_tracker = EmailTracker(
                    id=tracker_id,
                    campaign_id=campaign_id,
                    name=email_request.to_name,
                    company=email_request.company,
                    position=email_request.position,
                    email=email_request.to_email,
                    subject=email_request.subject,
                    body=email_request.html_content or email_request.text_content,
                    delivered=False,
                    recipient_email=email_request.to_email,
                    sender_email=email_request.from_email,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    delivery_status="draft"
                )
                db.add(db_tracker)
                saved_drafts.append(tracker_id)
        
        db.commit()
        
        logger.info(f"Auto-saved campaign {campaign_id} with {len(saved_drafts)} drafts")
        
        return {
            "success": True,
            "message": "Campaign auto-saved successfully",
            "campaign_id": campaign_id,
            "draft_count": len(saved_drafts),
            "saved_at": datetime.utcnow()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error auto-saving campaign: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to auto-save campaign: {str(e)}")
