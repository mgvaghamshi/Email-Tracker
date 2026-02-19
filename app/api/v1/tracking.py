"""
Tracking API endpoints for email opens, clicks, and events
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import uuid
import base64

from ...db import SessionLocal
from ...models import EmailTracker, EmailEvent, EmailClick
from ...email_schemas import (
    EmailEventResponse,
    EmailClickResponse,
    EmailTrackerResponse
)
from ...auth.jwt_auth import get_current_user, get_db
from ...database.user_models import User


router = APIRouter(prefix="/api/v1", tags=["tracking"])


# Authenticated tracking info endpoints

@router.get("/track/events/{tracker_id}", response_model=List[EmailEventResponse])
async def get_tracking_events(
    tracker_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all tracking events for a specific email tracker
    
    Returns all open, click, bounce, and other events associated with the tracker.
    Requires authentication.
    """
    # Check if tracker exists
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    
    # Get all events for this tracker
    events = db.query(EmailEvent).filter(EmailEvent.tracker_id == tracker_id).order_by(EmailEvent.timestamp.desc()).all()
    
    return events


@router.get("/track/clicks/{tracker_id}", response_model=List[EmailClickResponse])
async def get_click_events(
    tracker_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all click events for a specific email tracker
    
    Returns detailed information about all clicks on links in the tracked email.
    Requires authentication.
    """
    # Check if tracker exists
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    
    # Get all clicks for this tracker
    clicks = db.query(EmailClick).filter(EmailClick.tracker_id == tracker_id).order_by(EmailClick.timestamp.desc()).all()
    
    return clicks


@router.get("/track/pixel/{tracker_id}", response_model=EmailTrackerResponse)
async def get_tracking_pixel_info(
    tracker_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get tracking pixel information for a specific tracker
    
    Returns tracker details including open counts and timestamps.
    Requires authentication.
    """
    # Get tracker
    tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(status_code=404, detail="Tracker not found")
    
    return tracker


# Public tracking endpoints (no authentication required)

@router.get("/track/open/{tracker_id}")
async def track_email_open(
    tracker_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Track email opens via tracking pixel
    
    This endpoint is embedded in emails as a 1x1 transparent pixel image.
    When the email is opened, this endpoint is called automatically.
    No authentication required.
    
    Returns:
        A 1x1 transparent GIF image
    """
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
            tracker.open_count = 1
        else:
            tracker.open_count += 1
        
        # Create event
        event = EmailEvent(
            id=str(uuid.uuid4()),
            tracker_id=tracker_id,
            event_type="open",
            timestamp=datetime.utcnow(),
            user_agent=request.headers.get("user-agent", ""),
            ip_address=request.client.host if request.client else None
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


@router.get("/track/click/{tracker_id}")
async def track_email_click(
    tracker_id: str,
    url: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Track email clicks and redirect to original URL
    
    This endpoint is used to wrap links in emails for click tracking.
    When a recipient clicks a link, this endpoint records the click
    and redirects to the original URL. No authentication required.
    
    Args:
        tracker_id: The unique tracker ID for the email
        url: The original URL to redirect to (query parameter)
    
    Returns:
        HTTP 302 redirect to the original URL
    """
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
                ip_address=request.client.host if request.client else None
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
