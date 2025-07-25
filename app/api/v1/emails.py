"""
Email sending endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from ...dependencies import get_db, get_api_key
from ...database.models import EmailTracker
from ...schemas.email import (
    EmailSendRequest, EmailSendResponse, BulkEmailSendRequest,
    EmailTrackerResponse
)
from ...services.email_service import EmailService

router = APIRouter(prefix="/emails", tags=["Email Sending"])


@router.post("/send", response_model=EmailSendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_single_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> EmailSendResponse:
    """
    Send a single email with tracking
    
    This endpoint allows you to send a single email with full tracking capabilities.
    The email will be queued for immediate delivery unless a scheduled_at time is specified.
    
    **Features:**
    - Email open tracking via invisible pixel
    - Link click tracking with redirect
    - Bounce detection and handling
    - Delivery confirmation
    - Campaign grouping support
    - Scheduling support
    
    **Authentication:** Requires valid API key in Authorization header
    
    **Rate Limits:** Subject to your API key's rate limits
    
    **Example Usage:**
    ```bash
    curl -X POST "https://api.emailtracker.com/api/v1/emails/send" \\
         -H "Authorization: Bearer your_api_key" \\
         -H "Content-Type: application/json" \\
         -d '{
           "to_email": "user@example.com",
           "from_email": "sender@yourcompany.com",
           "from_name": "Your Company",
           "subject": "Welcome to our service!",
           "html_content": "<h1>Welcome!</h1><p>Thank you for signing up.</p>",
           "text_content": "Welcome! Thank you for signing up."
         }'
    ```
    """
    try:
        # Generate unique IDs
        tracker_id = str(uuid.uuid4())
        campaign_id = email_request.campaign_id or str(uuid.uuid4())
        
        # Create email tracker record
        db_tracker = EmailTracker(
            id=tracker_id,
            campaign_id=campaign_id,
            recipient_email=email_request.to_email,
            sender_email=email_request.from_email,
            subject=email_request.subject,
            html_content=email_request.html_content,
            text_content=email_request.text_content,
            delivered=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            scheduled_at=email_request.scheduled_at
        )
        db.add(db_tracker)
        db.commit()
        
        # Queue email for sending
        if email_request.scheduled_at is None or email_request.scheduled_at <= datetime.utcnow():
            # Send immediately
            background_tasks.add_task(send_email_task, email_request, tracker_id)
            status_msg = "queued"
            message = f"Email queued successfully for {email_request.to_email}"
        else:
            # Scheduled for later
            status_msg = "scheduled"
            message = f"Email scheduled for {email_request.scheduled_at}"
        
        return EmailSendResponse(
            success=True,
            message=message,
            tracker_id=tracker_id,
            campaign_id=campaign_id,
            status=status_msg
        )
        
    except Exception as e:
        return EmailSendResponse(
            success=False,
            message="Failed to send email",
            status="failed",
            error=str(e)
        )


@router.post("/send-bulk", response_model=EmailSendResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_bulk_emails(
    bulk_request: BulkEmailSendRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> EmailSendResponse:
    """
    Send bulk emails with tracking
    
    Send the same email to multiple recipients efficiently. Each email gets
    its own tracking ID while sharing the same campaign ID for analytics.
    
    **Features:**
    - Batch processing for efficiency
    - Individual tracking per recipient
    - Shared campaign analytics
    - Automatic rate limiting
    - Bounce handling per recipient
    
    **Limits:**
    - Maximum 1,000 recipients per request
    - Subject to API key rate limits
    - Large batches are automatically queued
    
    **Best Practices:**
    - Use smaller batches (100-500) for better performance
    - Include both HTML and text content
    - Use descriptive campaign IDs
    - Monitor deliverability stats
    
    **Example Usage:**
    ```bash
    curl -X POST "https://api.emailtracker.com/api/v1/emails/send-bulk" \\
         -H "Authorization: Bearer your_api_key" \\
         -H "Content-Type: application/json" \\
         -d '{
           "recipients": ["user1@example.com", "user2@example.com"],
           "from_email": "newsletter@yourcompany.com",
           "from_name": "Your Company Newsletter",
           "subject": "Monthly Newsletter - January 2025",
           "html_content": "<h1>Newsletter</h1><p>Check out this month updates!</p>",
           "campaign_id": "newsletter-january-2025"
         }'
    ```
    """
    try:
        if len(bulk_request.recipients) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 1,000 recipients allowed per bulk request"
            )
        
        tracker_ids = []
        campaign_id = bulk_request.campaign_id or str(uuid.uuid4())
        
        # Create tracker for each recipient
        for recipient in bulk_request.recipients:
            tracker_id = str(uuid.uuid4())
            tracker_ids.append(tracker_id)
            
            db_tracker = EmailTracker(
                id=tracker_id,
                campaign_id=campaign_id,
                recipient_email=recipient,
                sender_email=bulk_request.from_email,
                subject=bulk_request.subject,
                html_content=bulk_request.html_content,
                text_content=bulk_request.text_content,
                delivered=False,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(db_tracker)
            
            # Create individual email request
            email_request = EmailSendRequest(
                to_email=recipient,
                from_email=bulk_request.from_email,
                from_name=bulk_request.from_name,
                subject=bulk_request.subject,
                html_content=bulk_request.html_content,
                text_content=bulk_request.text_content,
                reply_to=bulk_request.reply_to,
                campaign_id=campaign_id
            )
            
            # Queue for sending
            background_tasks.add_task(send_email_task, email_request, tracker_id)
        
        db.commit()
        
        return EmailSendResponse(
            success=True,
            message=f"Bulk email queued for {len(bulk_request.recipients)} recipients",
            status="queued",
            campaign_id=campaign_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        return EmailSendResponse(
            success=False,
            message="Failed to send bulk emails",
            status="failed",
            error=str(e)
        )


@router.get("/trackers", response_model=List[EmailTrackerResponse])
async def list_email_trackers(
    campaign_id: str = None,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> List[EmailTrackerResponse]:
    """
    List email trackers
    
    Get a list of email trackers, optionally filtered by campaign ID.
    
    **Query Parameters:**
    - **campaign_id**: Filter by specific campaign (optional)
    - **limit**: Maximum number of results (default: 100, max: 1000)
    - **offset**: Number of results to skip for pagination (default: 0)
    
    **Example Usage:**
    ```bash
    # Get all trackers
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/emails/trackers"
         
    # Get trackers for specific campaign
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/emails/trackers?campaign_id=newsletter-january-2025"
         
    # Paginated results
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/emails/trackers?limit=50&offset=100"
    ```
    """
    try:
        if limit > 1000:
            limit = 1000
        
        query = db.query(EmailTracker)
        
        if campaign_id:
            query = query.filter(EmailTracker.campaign_id == campaign_id)
        
        trackers = query.order_by(EmailTracker.created_at.desc())\
                       .offset(offset)\
                       .limit(limit)\
                       .all()
        
        return [EmailTrackerResponse.from_orm(tracker) for tracker in trackers]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch trackers: {str(e)}"
        )


@router.get("/trackers/{tracker_id}", response_model=EmailTrackerResponse)
async def get_email_tracker(
    tracker_id: str,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> EmailTrackerResponse:
    """
    Get email tracker details
    
    Get detailed information about a specific email tracker including
    delivery status, engagement metrics, and timestamps.
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/emails/trackers/550e8400-e29b-41d4-a716-446655440000"
    ```
    """
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email tracker not found"
        )
    
    return EmailTrackerResponse.from_orm(tracker)


# Background task function
async def send_email_task(email_request: EmailSendRequest, tracker_id: str):
    """Background task to send email using EmailService"""
    try:
        email_service = EmailService()
        
        # Send the email
        success = await email_service.send_email(
            email_request=email_request,
            tracker_id=tracker_id
        )
        
        # Update tracker status
        from ...database.connection import SessionLocal
        db = SessionLocal()
        try:
            tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
            if tracker:
                tracker.delivered = success
                tracker.sent_at = datetime.utcnow() if success else None
                tracker.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
            
    except Exception as e:
        # Log error and update tracker
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in send_email_task: {str(e)}")
        
        from ...database.connection import SessionLocal
        db = SessionLocal()
        try:
            tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
            if tracker:
                tracker.delivered = False
                tracker.updated_at = datetime.utcnow()
                db.commit()
        finally:
            db.close()
