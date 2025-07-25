"""
Email tracking endpoints for opens, clicks, and pixel tracking
"""
from fastapi import APIRouter, Request, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import base64
import uuid
from datetime import datetime, timedelta

from ...dependencies import get_db, get_optional_api_key
from ...database.models import EmailTracker, EmailEvent, EmailClick
from ...schemas.tracking import (
    EmailEventResponse, EmailClickResponse, 
    TrackingPixelResponse, BotDetectionResponse
)
from ...services.tracking_service import TrackingService

router = APIRouter(prefix="/track", tags=["Tracking"])

# Initialize tracking service
tracking_service = TrackingService()

# 1x1 transparent GIF pixel data
TRACKING_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")


@router.get("/open/{tracker_id}", include_in_schema=False)
async def track_email_open(
    tracker_id: str, 
    request: Request, 
    db: Session = Depends(get_db)
):
    """
    Track email open event
    
    This endpoint is called automatically when an email is opened via an invisible
    tracking pixel. It records the open event with intelligent bot detection.
    
    **Note:** This endpoint is not meant to be called directly by API users.
    It's automatically embedded in emails as an invisible 1x1 pixel image.
    
    **Bot Detection:** Uses intelligent algorithms to filter out:
    - Search engine crawlers
    - Email security scanners
    - Automated testing tools
    - Duplicate rapid requests
    
    **Returns:** Always returns a 1x1 transparent GIF image
    """
    try:
        # Get tracker
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if not tracker:
            # Return pixel even if tracker not found to avoid broken images
            return Response(content=TRACKING_PIXEL, media_type="image/gif")
        
        # Extract request information
        user_agent = request.headers.get("user-agent", "")
        ip_address = request.client.host if request.client else None
        
        # Use tracking service for bot detection and event recording
        was_tracked = await tracking_service.track_open(
            tracker_id=tracker_id,
            user_agent=user_agent,
            ip_address=ip_address,
            db=db
        )
        
        # Always return tracking pixel regardless of whether we tracked the event
        return Response(
            content=TRACKING_PIXEL,
            media_type="image/gif",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
        
    except Exception as e:
        # Always return pixel even on error to avoid broken images
        return Response(content=TRACKING_PIXEL, media_type="image/gif")


@router.get("/click/{tracker_id}", include_in_schema=False)
async def track_email_click(
    tracker_id: str,
    url: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Track email click event and redirect
    
    This endpoint tracks link clicks and redirects to the intended destination.
    All links in tracked emails are automatically rewritten to go through this endpoint.
    
    **Note:** This endpoint is not meant to be called directly by API users.
    Links in emails are automatically rewritten to use this tracking endpoint.
    
    **Query Parameters:**
    - **url**: The original destination URL (automatically added)
    
    **Behavior:**
    1. Records the click event
    2. Redirects user to the original URL
    3. Handles duplicate click detection
    
    **Returns:** HTTP 302 redirect to the original URL
    """
    try:
        # Get tracker
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if tracker:
            # Extract request information
            user_agent = request.headers.get("user-agent", "")
            ip_address = request.client.host if request.client else None
            referrer = request.headers.get("referer")
            
            # Use tracking service to record click
            await tracking_service.track_click(
                tracker_id=tracker_id,
                url=url,
                user_agent=user_agent,
                ip_address=ip_address,
                referrer=referrer,
                db=db
            )
        
        # Always redirect to the actual URL
        return RedirectResponse(url=url, status_code=302)
        
    except Exception as e:
        # Still redirect to avoid broken links
        return RedirectResponse(url=url, status_code=302)


@router.get("/events/{tracker_id}", response_model=List[EmailEventResponse])
async def get_tracker_events(
    tracker_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(get_optional_api_key),
    db: Session = Depends(get_db)
) -> List[EmailEventResponse]:
    """
    Get tracking events for a specific email
    
    Retrieve all tracking events (opens, clicks, etc.) for a specific email tracker.
    
    **Path Parameters:**
    - **tracker_id**: The unique identifier for the email tracker
    
    **Query Parameters:**
    - **event_type**: Filter by event type: 'open', 'click', 'bounce', 'complaint' (optional)
    - **limit**: Maximum number of events to return (default: 100, max: 1000)
    - **offset**: Number of events to skip for pagination (default: 0)
    
    **Example Usage:**
    ```bash
    # Get all events for a tracker
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/track/events/550e8400-e29b-41d4-a716-446655440000"
         
    # Get only open events
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/track/events/550e8400-e29b-41d4-a716-446655440000?event_type=open"
    ```
    """
    try:
        # Check if tracker exists
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if not tracker:
            raise HTTPException(status_code=404, detail="Email tracker not found")
        
        if limit > 1000:
            limit = 1000
        
        # Build query
        query = db.query(EmailEvent).filter(EmailEvent.tracker_id == tracker_id)
        
        if event_type:
            query = query.filter(EmailEvent.event_type == event_type)
        
        # Get events
        events = query.order_by(EmailEvent.timestamp.desc())\
                      .offset(offset)\
                      .limit(limit)\
                      .all()
        
        return [EmailEventResponse.from_orm(event) for event in events]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch tracking events: {str(e)}"
        )


@router.get("/clicks/{tracker_id}", response_model=List[EmailClickResponse])
async def get_tracker_clicks(
    tracker_id: str,
    limit: int = 100,
    offset: int = 0,
    api_key: str = Depends(get_optional_api_key),
    db: Session = Depends(get_db)
) -> List[EmailClickResponse]:
    """
    Get click events for a specific email
    
    Retrieve all click events for a specific email tracker, including
    the URLs that were clicked and timing information.
    
    **Path Parameters:**
    - **tracker_id**: The unique identifier for the email tracker
    
    **Query Parameters:**
    - **limit**: Maximum number of clicks to return (default: 100, max: 1000)
    - **offset**: Number of clicks to skip for pagination (default: 0)
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/track/clicks/550e8400-e29b-41d4-a716-446655440000"
    ```
    """
    try:
        # Check if tracker exists
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if not tracker:
            raise HTTPException(status_code=404, detail="Email tracker not found")
        
        if limit > 1000:
            limit = 1000
        
        # Get clicks
        clicks = db.query(EmailClick)\
                   .filter(EmailClick.tracker_id == tracker_id)\
                   .order_by(EmailClick.timestamp.desc())\
                   .offset(offset)\
                   .limit(limit)\
                   .all()
        
        return [EmailClickResponse.from_orm(click) for click in clicks]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch click events: {str(e)}"
        )


@router.get("/pixel/{tracker_id}", response_model=TrackingPixelResponse)
async def get_tracking_pixel_info(
    tracker_id: str,
    api_key: str = Depends(get_optional_api_key),
    db: Session = Depends(get_db)
) -> TrackingPixelResponse:
    """
    Get tracking pixel information
    
    Get information about the tracking pixel for a specific email,
    including the pixel URL and whether the tracker is valid.
    
    **Path Parameters:**
    - **tracker_id**: The unique identifier for the email tracker
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/track/pixel/550e8400-e29b-41d4-a716-446655440000"
    ```
    """
    try:
        # Check if tracker exists
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        is_valid = tracker is not None
        
        # Build pixel URL
        from ...config import settings
        pixel_url = f"{settings.base_url}/api/v1/track/open/{tracker_id}"
        
        return TrackingPixelResponse(
            tracker_id=tracker_id,
            pixel_url=pixel_url,
            is_valid=is_valid
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get tracking pixel info: {str(e)}"
        )


@router.get("/debug/bot-detection", response_model=BotDetectionResponse)
async def debug_bot_detection(
    request: Request,
    user_agent: Optional[str] = None
) -> BotDetectionResponse:
    """
    Debug bot detection algorithm
    
    Test the bot detection algorithm with a specific user agent string
    or your current browser's user agent. Useful for testing and debugging.
    
    **Query Parameters:**
    - **user_agent**: Optional user agent string to test (uses your browser's if not provided)
    
    **Example Usage:**
    ```bash
    # Test your current browser
    curl "https://api.emailtracker.com/api/v1/track/debug/bot-detection"
    
    # Test a specific user agent
    curl "https://api.emailtracker.com/api/v1/track/debug/bot-detection?user_agent=Googlebot/2.1"
    ```
    """
    try:
        # Use provided user agent or get from request
        test_user_agent = user_agent or request.headers.get("user-agent", "")
        ip_address = request.client.host if request.client else None
        
        # Use tracking service for bot detection
        is_bot, bot_reason, confidence = tracking_service.detect_bot(test_user_agent, ip_address)
        
        return BotDetectionResponse(
            user_agent=test_user_agent,
            ip_address=ip_address,
            is_bot=is_bot,
            bot_reason=bot_reason,
            confidence=confidence
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze bot detection: {str(e)}"
        )


@router.get("/unsubscribe/{tracker_id}", include_in_schema=False)
async def unsubscribe(
    tracker_id: str, 
    db: Session = Depends(get_db)
):
    """
    Handle unsubscribe requests
    
    This endpoint handles unsubscribe requests for email recipients.
    
    **Note:** This endpoint is typically linked from email unsubscribe links
    and is not meant for direct API usage.
    """
    try:
        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
        if not tracker:
            return {"message": "Invalid unsubscribe link", "success": False}
        
        # Mark as unsubscribed
        tracker.unsubscribed = True
        tracker.updated_at = datetime.utcnow()
        
        # Create unsubscribe event
        event = EmailEvent(
            id=str(uuid.uuid4()),
            tracker_id=tracker_id,
            event_type="unsubscribe",
            timestamp=datetime.utcnow()
        )
        db.add(event)
        db.commit()
        
        return {
            "message": "Successfully unsubscribed",
            "success": True,
            "email": tracker.recipient_email
        }
        
    except Exception as e:
        return {
            "message": "Error processing unsubscribe request",
            "success": False,
            "error": str(e)
        }
