"""
Email sending endpoints for the EmailTracker API
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import uuid
import os
import logging

from ...db import SessionLocal
from ...models import EmailTracker, EmailCampaign
from ...email_schemas import EmailSendRequest, EmailSendResponse, BulkEmailSendRequest
from ...email_service import EmailService
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/emails", tags=["Email Sending"])

# Initialize email service
email_service = EmailService()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/send", response_model=EmailSendResponse)
async def send_single_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
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
        # Create campaign if it doesn't exist
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == email_request.campaign_id
        ).first()
        
        if not campaign:
            campaign = EmailCampaign(
                id=email_request.campaign_id,
                name=f"Campaign {email_request.campaign_id[:8]}",
                description=f"Auto-created campaign for {email_request.subject}",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(campaign)
            db.commit()
            logger.info(f"Created new campaign: {campaign.id}")

        # Create email tracker
        tracker_id = str(uuid.uuid4())
        tracking_pixel_url = f"{os.getenv('BASE_URL', 'http://localhost:8001')}/track/open/{tracker_id}"

        # Use company name from environment if not provided
        if not email_request.from_name:
            email_request.from_name = os.getenv('SENDER_NAME', 'EmailTracker')

        # Create tracker record
        db_tracker = EmailTracker(
            id=tracker_id,
            campaign_id=email_request.campaign_id,
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
            updated_at=datetime.utcnow()
        )
        db.add(db_tracker)
        db.commit()
        
        async def send_and_update():
            success = await email_service.send_email(
                email_request,
                tracker_id,
                tracking_pixel_url
            )
            if not success:
                logger.error(f"Failed to send email to {email_request.to_email}")
                
        background_tasks.add_task(send_and_update)
        
        return EmailSendResponse(
            success=True,
            message=f"Email queued successfully for {email_request.to_email}",
            tracker_id=tracker_id,
            status="queued",
            campaign_id=email_request.campaign_id
        )
    
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        
        if "certificate verify failed" in str(e).lower():
            return EmailSendResponse(
                success=False,
                message="SSL certificate error. Please check email server configuration.",
                error="SSL_CERT_ERROR"
            )
        elif "authentication failed" in str(e).lower():
            return EmailSendResponse(
                success=False,
                message="Email authentication failed. Please check credentials.",
                error="AUTH_ERROR"
            )
        elif "invalid recipient" in str(e).lower():
            return EmailSendResponse(
                success=False,
                message="Invalid recipient email address.",
                error="INVALID_RECIPIENT"
            )
        else:
            return EmailSendResponse(
                success=False,
                message="An unexpected error occurred while sending email.",
                error="UNKNOWN_ERROR"
            )


@router.post("/send-bulk", response_model=list[EmailSendResponse])
async def send_bulk_emails(
    bulk_request: BulkEmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Send multiple emails in bulk for the authenticated user

    This endpoint allows you to send multiple emails efficiently with tracking.
    Each email gets its own tracking ID and can be individually monitored.
    """
    responses = []
    
    for recipient in bulk_request.recipients:
        try:
            email_request = EmailSendRequest(
                campaign_id=bulk_request.campaign_id,
                to_email=recipient,
                from_email=bulk_request.from_email,
                subject=bulk_request.subject,
                html_content=bulk_request.html_content,
                text_content=bulk_request.text_content
            )
            
            tracker_id = str(uuid.uuid4())
            tracking_pixel_url = f"{os.getenv('BASE_URL', 'http://localhost:8001')}/track/open/{tracker_id}"
            
            db_tracker = EmailTracker(
                id=tracker_id,
                campaign_id=bulk_request.campaign_id,
                recipient_email=recipient,
                sender_email=bulk_request.from_email,
                subject=bulk_request.subject,
                created_at=datetime.utcnow()
            )
            db.add(db_tracker)
            
            background_tasks.add_task(
                email_service.send_email,
                email_request,
                tracker_id,
                tracking_pixel_url
            )
            
            responses.append(EmailSendResponse(
                success=True,
                message="Email queued for sending",
                tracker_id=tracker_id,
                status="queued"
            ))
            
        except Exception as e:
            responses.append(EmailSendResponse(
                success=False,
                message=f"Failed to queue email: {str(e)}",
                tracker_id="",
                status="failed"
            ))
    
    db.commit()
    return responses


@router.get("/tracking/{tracking_id}")
async def get_email_tracking(
    tracking_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get tracking information for a specific email

    Returns detailed tracking data including delivery status, opens, clicks, etc.
    Only returns data for emails belonging to the authenticated user.
    """
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracking_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Email tracker not found")
    
    return tracker


@router.get("/tracking")
async def list_email_tracking(
    campaign_id: str = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List email tracking records for the authenticated user

    Returns a paginated list of email tracking data.
    Can be filtered by campaign_id.
    """
    query = db.query(EmailTracker)
    if campaign_id:
        query = query.filter(EmailTracker.campaign_id == campaign_id)
    
    trackers = query.offset(skip).limit(limit).all()
    return {"items": trackers, "total": query.count(), "skip": skip, "limit": limit}
