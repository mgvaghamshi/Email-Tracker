"""
Email sending endpoints with user-based data isolation
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List
import uuid
import os
from datetime import datetime

from ...dependencies import get_db
from ...auth.api_key_auth import require_api_key_scope, get_user_from_api_key
from ...database.models import EmailTracker, Campaign
from ...database.user_models import User
from ...schemas.email import (
    EmailSendRequest, EmailSendResponse, BulkEmailSendRequest,
    EmailTrackerResponse
)
from ...services.email_service import EmailService
from ...core.logging_config import get_logger

logger = get_logger("api.emails")
router = APIRouter(prefix="/emails", tags=["Email Sending"])


@router.post("/send", response_model=EmailSendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_single_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(lambda: require_api_key_scope("emails:send")),
    db: Session = Depends(get_db)
) -> EmailSendResponse:
    """
    Send a single email with tracking for the authenticated user
    
    This endpoint allows you to send a single email with full tracking capabilities.
    The email will be queued for immediate delivery unless a scheduled_at time is specified.
    
    **Features:**
    - Email open tracking via invisible pixel
    - Link click tracking with redirect
    - Bounce detection and handling
    - Delivery confirmation
    - Campaign grouping support
    - Scheduling support
    
    **Authentication:** Requires valid JWT token in Authorization header
    
    **Rate Limits:** Subject to your account's rate limits
    """
    try:
        # Verify campaign belongs to user if specified
        if email_request.campaign_id:
            campaign = db.query(Campaign).filter(
                Campaign.id == email_request.campaign_id,
                Campaign.user_id == current_user.id
            ).first()
            
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Generate tracking ID
        tracking_id = str(uuid.uuid4())
        
        # Create email tracker record
        email_tracker = EmailTracker(
            id=tracking_id,
            user_id=current_user.id,
            campaign_id=email_request.campaign_id,
            recipient_email=email_request.to_email,
            subject=email_request.subject,
            status="queued",
            created_at=datetime.utcnow()
        )
        
        db.add(email_tracker)
        db.commit()
        
        # Initialize email service
        email_service = EmailService()
        
        # Send email in background
        background_tasks.add_task(
            email_service.send_email,
            email_request,
            tracking_id,
            current_user.id
        )
        
        return EmailSendResponse(
            tracking_id=tracking_id,
            status="queued",
            message="Email queued for delivery"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")


@router.post("/send-bulk", response_model=List[EmailSendResponse], status_code=status.HTTP_202_ACCEPTED)
async def send_bulk_emails(
    bulk_request: BulkEmailSendRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(lambda: require_api_key_scope("emails:send")),
    db: Session = Depends(get_db)
) -> List[EmailSendResponse]:
    """
    Send multiple emails in bulk for the authenticated user
    
    This endpoint allows you to send multiple emails efficiently with tracking.
    Each email gets its own tracking ID and can be individually monitored.
    """
    try:
        # Verify campaign belongs to user if specified
        if bulk_request.campaign_id:
            campaign = db.query(Campaign).filter(
                Campaign.id == bulk_request.campaign_id,
                Campaign.user_id == current_user.id
            ).first()
            
            if not campaign:
                raise HTTPException(status_code=404, detail="Campaign not found")
        
        responses = []
        email_service = EmailService()
        
        for email_request in bulk_request.emails:
            # Generate tracking ID
            tracking_id = str(uuid.uuid4())
            
            # Create email tracker record
            email_tracker = EmailTracker(
                id=tracking_id,
                user_id=current_user.id,
                campaign_id=bulk_request.campaign_id,
                recipient_email=email_request.to_email,
                subject=email_request.subject,
                status="queued",
                created_at=datetime.utcnow()
            )
            
            db.add(email_tracker)
            
            # Send email in background
            background_tasks.add_task(
                email_service.send_email,
                email_request,
                tracking_id,
                current_user.id
            )
            
            responses.append(EmailSendResponse(
                tracking_id=tracking_id,
                status="queued",
                message="Email queued for delivery"
            ))
        
        db.commit()
        return responses
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send bulk emails: {str(e)}")


@router.get("/tracking/{tracking_id}", response_model=EmailTrackerResponse)
async def get_email_tracking(
    tracking_id: str,
    current_user: User = Depends(lambda: require_api_key_scope("emails:read")),
    db: Session = Depends(get_db)
) -> EmailTrackerResponse:
    """
    Get tracking information for a specific email
    
    Returns detailed tracking data including delivery status, opens, clicks, etc.
    Only returns data for emails belonging to the authenticated user.
    """
    email_tracker = db.query(EmailTracker).filter(
        EmailTracker.id == tracking_id,
        EmailTracker.user_id == current_user.id
    ).first()
    
    if not email_tracker:
        raise HTTPException(status_code=404, detail="Email tracking not found")
    
    return EmailTrackerResponse(
        tracking_id=email_tracker.id,
        campaign_id=email_tracker.campaign_id,
        recipient_email=email_tracker.recipient_email,
        subject=email_tracker.subject,
        status=email_tracker.status,
        delivered=email_tracker.delivered,
        delivered_at=email_tracker.delivered_at,
        opened=email_tracker.opened,
        opened_at=email_tracker.opened_at,
        clicked=email_tracker.clicked,
        clicked_at=email_tracker.clicked_at,
        bounced=email_tracker.bounced,
        bounced_at=email_tracker.bounced_at,
        unsubscribed=email_tracker.unsubscribed,
        unsubscribed_at=email_tracker.unsubscribed_at,
        created_at=email_tracker.created_at,
        updated_at=email_tracker.updated_at
    )


@router.get("/tracking", response_model=List[EmailTrackerResponse])
async def list_email_tracking(
    campaign_id: str = None,
    limit: int = 50,
    offset: int = 0,
    current_user: User = Depends(lambda: require_api_key_scope("emails:read")),
    db: Session = Depends(get_db)
) -> List[EmailTrackerResponse]:
    """
    List email tracking records for the authenticated user
    
    Returns a paginated list of email tracking data.
    Can be filtered by campaign_id.
    """
    query = db.query(EmailTracker).filter(EmailTracker.user_id == current_user.id)
    
    if campaign_id:
        # Verify campaign belongs to user
        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        query = query.filter(EmailTracker.campaign_id == campaign_id)
    
    email_trackers = query.offset(offset).limit(limit).all()
    
    return [
        EmailTrackerResponse(
            tracking_id=tracker.id,
            campaign_id=tracker.campaign_id,
            recipient_email=tracker.recipient_email,
            subject=tracker.subject,
            status=tracker.status,
            delivered=tracker.delivered,
            delivered_at=tracker.delivered_at,
            opened=tracker.opened,
            opened_at=tracker.opened_at,
            clicked=tracker.clicked,
            clicked_at=tracker.clicked_at,
            bounced=tracker.bounced,
            bounced_at=tracker.bounced_at,
            unsubscribed=tracker.unsubscribed,
            unsubscribed_at=tracker.unsubscribed_at,
            created_at=tracker.created_at,
            updated_at=tracker.updated_at
        )
        for tracker in email_trackers
    ]
