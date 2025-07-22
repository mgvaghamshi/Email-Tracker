from fastapi import FastAPI, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
import hashlib
import os
from contextlib import asynccontextmanager

import logging
logger = logging.getLogger(__name__)


from .database import SessionLocal, engine, Base, init_db
from .models import EmailCampaign, EmailTracker, EmailEvent, EmailBounce, EmailClick, EmailTemplate, EmailList, EmailSubscriber
from .schemas import (
    EmailCampaignCreate, EmailCampaignResponse, EmailTrackerCreate, 
    EmailTrackerResponse, EmailEventResponse, EmailAnalytics,
    EmailSendRequest, EmailSendResponse, BulkEmailSendRequest,
    EmailTemplateCreate, EmailTemplateResponse, EmailListCreate,
    EmailListResponse, EmailSubscriberCreate, EmailSubscriberResponse,EmailCampaignWithStats,CampaignTrackingResponse, CampaignUpdate
)
from .email_service import EmailService

# Initialize database tables
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass

app = FastAPI(
    title="Email Tracker API",
    description="A comprehensive email tracking API similar to Mailgun",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Initialize email service
email_service = EmailService()

@app.get("/")
async def root():
    return {"message": "Email Tracker API is running"}

@app.post("/campaigns/", response_model=EmailCampaignResponse)
async def create_campaign(
    campaign: EmailCampaignCreate,
    db: Session = Depends(get_db)
):
    """Create a new email campaign"""
    db_campaign = EmailCampaign(
        id=str(uuid.uuid4()),
        name=campaign.name,
        description=campaign.description,
        created_at=datetime.utcnow()
    )
    db.add(db_campaign)
    db.commit()
    db.refresh(db_campaign)
    return db_campaign

@app.put("/campaigns/{campaign_id}", response_model=EmailCampaignResponse)
async def update_campaign(
    campaign_id: str,
    campaign_update: CampaignUpdate,
    db: Session = Depends(get_db)
):
    """Update an existing campaign"""
    # Find the campaign
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    
    if not campaign:
        # Try to create campaign from tracker data
        tracker = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).first()
        
        if tracker:
            campaign = EmailCampaign(
                id=campaign_id,
                name=f"Campaign {campaign_id[:8]}",
                description="Auto-created from existing tracker",
                created_at=tracker.created_at,
                updated_at=datetime.utcnow()
            )
            db.add(campaign)
            db.commit()
            logger.info(f"Created missing campaign: {campaign_id}")
        else:
            raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Update only provided fields
    if campaign_update.sent is not None:
        campaign.sent = campaign_update.sent
    if campaign_update.name is not None:
        campaign.name = campaign_update.name
    if campaign_update.description is not None:
        campaign.description = campaign_update.description
    
    # Always update the updated_at timestamp
    campaign.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    db.refresh(campaign)
    
    return campaign

@app.get("/campaigns/", response_model=List[CampaignTrackingResponse])
async def get_campaigns(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all email campaigns with tracking details"""
    # Query trackers with campaign join
    trackers = db.query(EmailTracker).join(
        EmailCampaign,
        EmailTracker.campaign_id == EmailCampaign.id,
        isouter=True  # Left outer join
    ).offset(skip).limit(limit).all()
    
    # Format response
    result = []
    for tracker in trackers:
        result.append({
            "id": tracker.id,
            "name": tracker.name,
            "company": tracker.company,
            "position": tracker.position,
            "email": tracker.recipient_email,
            "subject": tracker.subject,
            "content": tracker.body,
            "sent": tracker.delivered,
            "created_at": tracker.sent_at or tracker.created_at,
            "updated_at": tracker.updated_at or tracker.created_at,
            "campaign_id": tracker.campaign_id,
            "campaign_name": tracker.campaign.name if tracker.campaign else None,
            "campaign_description": tracker.campaign.description if tracker.campaign else None
        })
    
    return result

@app.get("/campaigns/{campaign_id}", response_model=EmailCampaignResponse)
async def get_campaign(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific campaign with statistics"""
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get trackers for this campaign
    trackers = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id).all()
    
    # Calculate stats
    total_sent = len(trackers)
    total_opens = sum(1 for t in trackers if t.opened_at)
    total_clicks = sum(t.click_count for t in trackers)
    
    # Add stats to campaign
    campaign_dict = {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "created_at": campaign.created_at,
        "total_sent": total_sent,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "open_rate": round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2),
        "click_rate": round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2)
    }
    
    return campaign_dict
@app.get("/campaigns/recent", response_model=List[EmailCampaignResponse])
async def get_recent_campaigns(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get campaigns with recent email activity"""
    from datetime import datetime, timedelta
    
    # Get campaigns that have emails sent in the last N days
    recent_date = datetime.utcnow() - timedelta(days=days)
    
    campaigns_with_recent_activity = db.query(EmailCampaign).join(
        EmailTracker, EmailCampaign.id == EmailTracker.campaign_id
    ).filter(
        EmailTracker.created_at >= recent_date
    ).distinct().all()
    
    campaigns_with_stats = []
    for campaign in campaigns_with_recent_activity:
        # Get recent trackers
        trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign.id,
            EmailTracker.created_at >= recent_date
        ).all()
        
        total_sent = len(trackers)
        total_opens = sum(1 for t in trackers if t.opened_at)
        total_clicks = sum(t.click_count for t in trackers)
        
        campaign_dict = {
            "id": campaign.id,
            "name": campaign.name,
            "description": campaign.description,
            "created_at": campaign.created_at,
            "total_sent": total_sent,
            "total_opens": total_opens,
            "total_clicks": total_clicks,
            "open_rate": round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2),
            "click_rate": round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2),
            "last_email_sent": max((t.created_at for t in trackers), default=None)
        }
        campaigns_with_stats.append(campaign_dict)
    
    return campaigns_with_stats

@app.post("/send-email/", response_model=EmailSendResponse)
async def send_email(
    email_request: EmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send a single email with tracking"""
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
        tracking_pixel_url = f"{os.getenv('BASE_URL')}/track/open/{tracker_id}"

        # Use company name from environment if not provided
        if not email_request.from_name:
            email_request.from_name = os.getenv('SENDER_NAME')

        # Create tracker record
        db_tracker = EmailTracker(
            id=tracker_id,
            campaign_id=email_request.campaign_id,
            name=email_request.to_name,  # Add recipient name
            company=email_request.company,  # Add company
            position=email_request.position,  # Add position
            email=email_request.to_email,  # Required email field
            subject=email_request.subject,
            body=email_request.html_content or email_request.text_content,  # Store content
            delivered=False,  # Will be updated after sending
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
        
        # Return appropriate error messages based on error type
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

@app.post("/send-bulk-email/", response_model=List[EmailSendResponse])
async def send_bulk_email(
    bulk_request: BulkEmailSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Send bulk emails with tracking"""
    responses = []
    
    for recipient in bulk_request.recipients:
        try:
            # Create individual email request
            email_request = EmailSendRequest(
                campaign_id=bulk_request.campaign_id,
                to_email=recipient,
                from_email=bulk_request.from_email,
                subject=bulk_request.subject,
                html_content=bulk_request.html_content,
                text_content=bulk_request.text_content
            )
            
            # Create email tracker
            tracker_id = str(uuid.uuid4())
            tracking_pixel_url = f"{os.getenv('BASE_URL')}/track/open/{tracker_id}"
            
            # Create tracker record
            db_tracker = EmailTracker(
                id=tracker_id,
                campaign_id=bulk_request.campaign_id,
                recipient_email=recipient,
                sender_email=bulk_request.from_email,
                subject=bulk_request.subject,
                created_at=datetime.utcnow()
            )
            db.add(db_tracker)
            
            # Send email in background
            background_tasks.add_task(
                email_service.send_email,
                email_request,
                tracker_id,
                tracking_pixel_url
            )
            
            responses.append(EmailSendResponse(
                message="Email queued for sending",
                tracker_id=tracker_id,
                status="queued"
            ))
            
        except Exception as e:
            responses.append(EmailSendResponse(
                message=f"Failed to queue email: {str(e)}",
                tracker_id="",
                status="failed"
            ))
    
    db.commit()
    return responses

@app.get("/track/open/{tracker_id}")
async def track_email_open(
    tracker_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Track email opens via tracking pixel"""
    try:
        # Get tracker
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if not tracker:
            # Return 1x1 transparent pixel even if tracker not found
            return Response(
                content=base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
                media_type="image/gif"
            )
        
        # Update tracker
        if not tracker.opened_at:
            tracker.opened_at = datetime.utcnow()
            tracker.open_count += 1
        else:
            tracker.open_count += 1
        
        # Create event
        event = EmailEvent(
            id=str(uuid.uuid4()),
            tracker_id=tracker_id,
            event_type="open",
            timestamp=datetime.utcnow(),
            user_agent=request.headers.get("user-agent", ""),
            ip_address=request.client.host
        )
        db.add(event)
        db.commit()
        
        # Return 1x1 transparent pixel
        return Response(
            content=base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
            media_type="image/gif"
        )
    
    except Exception as e:
        # Always return pixel even on error
        return Response(
            content=base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"),
            media_type="image/gif"
        )

@app.get("/track/click/{tracker_id}")
async def track_email_click(
    tracker_id: str,
    url: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """Track email clicks and redirect to original URL"""
    try:
        # Get tracker
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if tracker:
            # Update tracker
            tracker.click_count += 1
            
            # Create event
            event = EmailEvent(
                id=str(uuid.uuid4()),
                tracker_id=tracker_id,
                event_type="click",
                timestamp=datetime.utcnow(),
                user_agent=request.headers.get("user-agent", ""),
                ip_address=request.client.host
            )
            db.add(event)
            
            # Create click record
            click = EmailClick(
                id=str(uuid.uuid4()),
                tracker_id=tracker_id,
                url=url,
                timestamp=datetime.utcnow()
            )
            db.add(click)
            db.commit()
        
        # Redirect to original URL
        return Response(
            status_code=302,
            headers={"Location": url}
        )
    
    except Exception as e:
        # Redirect to URL even on error
        return Response(
            status_code=302,
            headers={"Location": url}
        )

@app.get("/trackers/", response_model=List[EmailTrackerResponse])
async def get_trackers(
    campaign_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get email trackers"""
    query = db.query(EmailTracker)
    if campaign_id:
        query = query.filter(EmailTracker.campaign_id == campaign_id)
    
    trackers = query.offset(skip).limit(limit).all()
    return trackers

@app.get("/trackers/{tracker_id}", response_model=EmailTrackerResponse)
async def get_tracker(
    tracker_id: str,
    db: Session = Depends(get_db)
):
    """Get specific email tracker"""
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    return tracker

@app.get("/trackers/{tracker_id}/events", response_model=List[EmailEventResponse])
async def get_tracker_events(
    tracker_id: str,
    db: Session = Depends(get_db)
):
    """Get events for a specific tracker"""
    events = db.query(EmailEvent).filter(EmailEvent.tracker_id == tracker_id).all()
    return events

@app.get("/campaigns/{campaign_id}/analytics", response_model=EmailAnalytics)
async def get_campaign_analytics(
    campaign_id: str,
    db: Session = Depends(get_db)
):
    """Get analytics for a campaign"""
    # Get campaign
    campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get trackers for this campaign
    trackers = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id).all()
    
    # Calculate analytics
    total_sent = len(trackers)
    total_opens = sum(1 for t in trackers if t.opened_at)
    total_clicks = sum(t.click_count for t in trackers)
    total_bounces = db.query(EmailBounce).join(EmailTracker).filter(
        EmailTracker.campaign_id == campaign_id
    ).count()
    
    # Calculate rates
    open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
    click_rate = (total_clicks / total_sent * 100) if total_sent > 0 else 0
    bounce_rate = (total_bounces / total_sent * 100) if total_sent > 0 else 0
    
    return EmailAnalytics(
        campaign_id=campaign_id,
        total_sent=total_sent,
        total_opens=total_opens,
        total_clicks=total_clicks,
        total_bounces=total_bounces,
        open_rate=round(open_rate, 2),
        click_rate=round(click_rate, 2),
        bounce_rate=round(bounce_rate, 2)
    )

@app.post("/webhooks/bounce")
async def handle_bounce_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle bounce webhooks from email service"""
    try:
        data = await request.json()
        
        # Create bounce record
        bounce = EmailBounce(
            id=str(uuid.uuid4()),
            tracker_id=data.get("tracker_id"),
            bounce_type=data.get("bounce_type", "hard"),
            reason=data.get("reason", ""),
            timestamp=datetime.utcnow()
        )
        db.add(bounce)
        db.commit()
        
        return {"status": "success"}
    
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Additional endpoints to add to main.py

# Template endpoints
@app.post("/templates/", response_model=EmailTemplateResponse)
async def create_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db)
):
    """Create a new email template"""
    from models import EmailTemplate
    
    db_template = EmailTemplate(
        id=str(uuid.uuid4()),
        name=template.name,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        created_at=datetime.utcnow()
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template

@app.get("/templates/", response_model=List[EmailTemplateResponse])
async def get_templates(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all email templates"""
    from models import EmailTemplate
    templates = db.query(EmailTemplate).filter(
        EmailTemplate.is_active == True
    ).offset(skip).limit(limit).all()
    return templates

@app.get("/templates/{template_id}", response_model=EmailTemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific template"""
    from models import EmailTemplate
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@app.put("/templates/{template_id}", response_model=EmailTemplateResponse)
async def update_template(
    template_id: str,
    template_update: EmailTemplateCreate,
    db: Session = Depends(get_db)
):
    """Update a template"""
    from models import EmailTemplate
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.name = template_update.name
    template.subject = template_update.subject
    template.html_content = template_update.html_content
    template.text_content = template_update.text_content
    template.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(template)
    return template

@app.delete("/templates/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db)
):
    """Delete a template (soft delete)"""
    from models import EmailTemplate
    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template.is_active = False
    template.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Template deleted successfully"}

# Email list endpoints
@app.post("/lists/", response_model=EmailListResponse)
async def create_email_list(
    email_list: EmailListCreate,
    db: Session = Depends(get_db)
):
    """Create a new email list"""
    from models import EmailList
    
    db_list = EmailList(
        id=str(uuid.uuid4()),
        name=email_list.name,
        description=email_list.description,
        created_at=datetime.utcnow()
    )
    db.add(db_list)
    db.commit()
    db.refresh(db_list)
    return db_list

@app.get("/lists/", response_model=List[EmailListResponse])
async def get_email_lists(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all email lists"""
    from models import EmailList
    lists = db.query(EmailList).offset(skip).limit(limit).all()
    return lists

@app.get("/lists/{list_id}", response_model=EmailListResponse)
async def get_email_list(
    list_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific email list"""
    from models import EmailList
    email_list = db.query(EmailList).filter(EmailList.id == list_id).first()
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    return email_list

# Subscriber endpoints
@app.post("/lists/{list_id}/subscribers/", response_model=EmailSubscriberResponse)
async def add_subscriber(
    list_id: str,
    subscriber: EmailSubscriberCreate,
    db: Session = Depends(get_db)
):
    """Add a subscriber to an email list"""
    from models import EmailList, EmailSubscriber
    
    # Check if list exists
    email_list = db.query(EmailList).filter(EmailList.id == list_id).first()
    if not email_list:
        raise HTTPException(status_code=404, detail="Email list not found")
    
    # Check if subscriber already exists
    existing_subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.email_list_id == list_id,
        EmailSubscriber.email == subscriber.email
    ).first()
    
    if existing_subscriber:
        if existing_subscriber.is_active:
            raise HTTPException(
                status_code=400, 
                detail="Subscriber already exists in this list"
            )
        else:
            # Reactivate existing subscriber
            existing_subscriber.is_active = True
            existing_subscriber.subscribed_at = datetime.utcnow()
            existing_subscriber.unsubscribed_at = None
            db.commit()
            db.refresh(existing_subscriber)
            return existing_subscriber
    
    # Create new subscriber
    db_subscriber = EmailSubscriber(
        id=str(uuid.uuid4()),
        email_list_id=list_id,
        email=subscriber.email,
        first_name=subscriber.first_name,
        last_name=subscriber.last_name,
        subscribed_at=datetime.utcnow()
    )
    db.add(db_subscriber)
    db.commit()
    db.refresh(db_subscriber)
    return db_subscriber

@app.get("/lists/{list_id}/subscribers/", response_model=List[EmailSubscriberResponse])
async def get_subscribers(
    list_id: str,
    active_only: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get subscribers from an email list"""
    from models import EmailSubscriber
    
    query = db.query(EmailSubscriber).filter(
        EmailSubscriber.email_list_id == list_id
    )
    
    if active_only:
        query = query.filter(EmailSubscriber.is_active == True)
    
    subscribers = query.offset(skip).limit(limit).all()
    return subscribers

@app.delete("/lists/{list_id}/subscribers/{subscriber_id}")
async def unsubscribe(
    list_id: str,
    subscriber_id: str,
    db: Session = Depends(get_db)
):
    """Unsubscribe a subscriber from an email list"""
    from models import EmailSubscriber
    
    subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.id == subscriber_id,
        EmailSubscriber.email_list_id == list_id
    ).first()
    
    if not subscriber:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    
    subscriber.is_active = False
    subscriber.unsubscribed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Subscriber unsubscribed successfully"}

# Unsubscribe endpoint for tracking links
@app.get("/unsubscribe/{tracker_id}")
async def unsubscribe_via_tracker(
    tracker_id: str,
    db: Session = Depends(get_db)
):
    """Unsubscribe via tracker ID"""
    from models import EmailTracker, EmailSubscriber
    
    # Get tracker
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    
    # Find and unsubscribe user
    subscriber = db.query(EmailSubscriber).filter(
        EmailSubscriber.email == tracker.recipient_email
    ).first()
    
    if subscriber:
        subscriber.is_active = False
        subscriber.unsubscribed_at = datetime.utcnow()
        db.commit()
    
    return {"message": "You have been unsubscribed successfully"}

# Advanced analytics endpoints
@app.get("/analytics/overview")
async def get_analytics_overview(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get overall analytics overview"""
    from .models import EmailTracker, EmailEvent
    
    # Parse dates
    start_dt = datetime.fromisoformat(start_date) if start_date else datetime.utcnow() - timedelta(days=30)
    end_dt = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
    
    # Get trackers in date range
    trackers = db.query(EmailTracker).filter(
        EmailTracker.created_at >= start_dt,
        EmailTracker.created_at <= end_dt
    ).all()
    
    # Calculate metrics
    total_sent = len(trackers)
    total_opens = sum(1 for t in trackers if t.opened_at)
    total_clicks = sum(t.click_count for t in trackers)
    
    # Get events
    events = db.query(EmailEvent).filter(
        EmailEvent.timestamp >= start_dt,
        EmailEvent.timestamp <= end_dt
    ).all()
    
    # Group events by type
    event_counts = {}
    for event in events:
        event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
    
    return {
        "total_sent": total_sent,
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "open_rate": round((total_opens / total_sent * 100) if total_sent > 0 else 0, 2),
        "click_rate": round((total_clicks / total_sent * 100) if total_sent > 0 else 0, 2),
        "event_counts": event_counts,
        "date_range": {
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat()
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        db.execute("SELECT 1")
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)