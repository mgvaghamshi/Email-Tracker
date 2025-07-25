"""
Webhook management and delivery endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime, timedelta
import json
import httpx
import hashlib
import hmac

from ...dependencies import get_db, get_api_key
from ...database.models import WebhookEvent
from ...config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


class WebhookSchema:
    """Webhook-related schemas"""
    
    class WebhookEventCreate:
        def __init__(self, url: str, events: List[str], secret: str = None):
            self.url = url
            self.events = events  # ['email.sent', 'email.opened', 'email.clicked', etc.]
            self.secret = secret
    
    class WebhookEventResponse:
        def __init__(self, id: str, url: str, event_type: str, delivered: bool, 
                     created_at: datetime, delivery_attempts: int = 0):
            self.id = id
            self.url = url
            self.event_type = event_type
            self.delivered = delivered
            self.created_at = created_at
            self.delivery_attempts = delivery_attempts


@router.post("/events/send", status_code=status.HTTP_202_ACCEPTED)
async def send_webhook_event(
    webhook_url: str,
    event_type: str,
    payload: Dict[str, Any],
    secret: str = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Send a webhook event
    
    Queue a webhook event for delivery to the specified URL. The webhook
    will be delivered asynchronously with automatic retries on failure.
    
    **Request Body:**
    - **webhook_url**: The URL to deliver the webhook to
    - **event_type**: Type of event (e.g., 'email.sent', 'email.opened')
    - **payload**: The webhook payload data
    - **secret**: Optional secret for signature verification
    
    **Webhook Delivery:**
    - Automatic retries with exponential backoff
    - Signature verification support
    - Delivery confirmation tracking
    
    **Example Usage:**
    ```bash
    curl -X POST "https://api.emailtracker.com/api/v1/webhooks/events/send" \\
         -H "Authorization: Bearer your_api_key" \\
         -H "Content-Type: application/json" \\
         -d '{
           "webhook_url": "https://yourapp.com/webhooks/email",
           "event_type": "email.opened",
           "payload": {
             "tracker_id": "550e8400-e29b-41d4-a716-446655440000",
             "campaign_id": "newsletter-january-2025",
             "recipient": "user@example.com",
             "timestamp": "2025-01-25T10:05:00Z"
           },
           "secret": "your_webhook_secret"
         }'
    ```
    """
    try:
        # Create webhook event record
        webhook_event = WebhookEvent(
            webhook_url=webhook_url,
            event_type=event_type,
            payload=json.dumps(payload),
            delivered=False,
            delivery_attempts=0,
            next_attempt_at=datetime.utcnow()
        )
        
        db.add(webhook_event)
        db.commit()
        db.refresh(webhook_event)
        
        # Queue for delivery
        background_tasks.add_task(
            deliver_webhook,
            webhook_event.id,
            webhook_url,
            event_type,
            payload,
            secret
        )
        
        return {
            "success": True,
            "message": "Webhook event queued for delivery",
            "webhook_event_id": webhook_event.id
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to queue webhook event: {str(e)}"
        )


@router.get("/events", response_model=List[Dict[str, Any]])
async def list_webhook_events(
    limit: int = 100,
    offset: int = 0,
    delivered: bool = None,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    List webhook events
    
    Get a list of webhook events with their delivery status.
    
    **Query Parameters:**
    - **limit**: Maximum number of events to return (default: 100, max: 1000)
    - **offset**: Number of events to skip for pagination (default: 0)
    - **delivered**: Filter by delivery status (optional)
    
    **Example Usage:**
    ```bash
    # Get all webhook events
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/webhooks/events"
         
    # Get only failed deliveries
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/webhooks/events?delivered=false"
    ```
    """
    try:
        if limit > 1000:
            limit = 1000
        
        query = db.query(WebhookEvent)
        
        if delivered is not None:
            query = query.filter(WebhookEvent.delivered == delivered)
        
        events = query.order_by(WebhookEvent.created_at.desc())\
                      .offset(offset)\
                      .limit(limit)\
                      .all()
        
        return [
            {
                "id": event.id,
                "webhook_url": event.webhook_url,
                "event_type": event.event_type,
                "delivered": event.delivered,
                "delivery_attempts": event.delivery_attempts,
                "created_at": event.created_at.isoformat(),
                "last_attempt_at": event.last_attempt_at.isoformat() if event.last_attempt_at else None,
                "response_status": event.response_status,
                "response_body": event.response_body[:200] if event.response_body else None  # Truncate for display
            }
            for event in events
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list webhook events: {str(e)}"
        )


@router.get("/events/{event_id}")
async def get_webhook_event(
    event_id: str,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get webhook event details
    
    Get detailed information about a specific webhook event including
    delivery attempts and response data.
    
    **Path Parameters:**
    - **event_id**: Unique webhook event identifier
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/webhooks/events/webhook_550e8400-e29b-41d4-a716-446655440000"
    ```
    """
    try:
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Webhook event not found")
        
        return {
            "id": event.id,
            "webhook_url": event.webhook_url,
            "event_type": event.event_type,
            "payload": json.loads(event.payload),
            "delivered": event.delivered,
            "delivery_attempts": event.delivery_attempts,
            "created_at": event.created_at.isoformat(),
            "last_attempt_at": event.last_attempt_at.isoformat() if event.last_attempt_at else None,
            "next_attempt_at": event.next_attempt_at.isoformat() if event.next_attempt_at else None,
            "response_status": event.response_status,
            "response_body": event.response_body
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get webhook event: {str(e)}"
        )


@router.post("/events/{event_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_webhook_event(
    event_id: str,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
):
    """
    Retry webhook event delivery
    
    Manually retry delivery of a failed webhook event.
    
    **Path Parameters:**
    - **event_id**: Unique webhook event identifier
    
    **Example Usage:**
    ```bash
    curl -X POST -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/webhooks/events/webhook_550e8400-e29b-41d4-a716-446655440000/retry"
    ```
    """
    try:
        event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
        if not event:
            raise HTTPException(status_code=404, detail="Webhook event not found")
        
        if event.delivered:
            raise HTTPException(status_code=400, detail="Webhook event already delivered")
        
        # Parse payload
        payload = json.loads(event.payload)
        
        # Queue for retry
        background_tasks.add_task(
            deliver_webhook,
            event.id,
            event.webhook_url,
            event.event_type,
            payload,
            None  # No secret for retry
        )
        
        return {
            "success": True,
            "message": "Webhook event queued for retry"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry webhook event: {str(e)}"
        )


@router.post("/test")
async def test_webhook_endpoint(
    webhook_url: str,
    secret: str = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    api_key: str = Depends(get_api_key)
):
    """
    Test a webhook endpoint
    
    Send a test webhook event to verify your endpoint is working correctly.
    
    **Request Body:**
    - **webhook_url**: The URL to test
    - **secret**: Optional secret for signature verification
    
    **Example Usage:**
    ```bash
    curl -X POST "https://api.emailtracker.com/api/v1/webhooks/test" \\
         -H "Authorization: Bearer your_api_key" \\
         -H "Content-Type: application/json" \\
         -d '{
           "webhook_url": "https://yourapp.com/webhooks/email",
           "secret": "your_webhook_secret"
         }'
    ```
    """
    try:
        # Create test payload
        test_payload = {
            "event_type": "webhook.test",
            "timestamp": datetime.utcnow().isoformat(),
            "test": True,
            "message": "This is a test webhook from EmailTracker API"
        }
        
        # Queue for delivery
        background_tasks.add_task(
            deliver_webhook,
            f"test_{datetime.utcnow().timestamp()}",
            webhook_url,
            "webhook.test",
            test_payload,
            secret
        )
        
        return {
            "success": True,
            "message": "Test webhook queued for delivery",
            "test_payload": test_payload
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test webhook: {str(e)}"
        )


# Background task for webhook delivery
async def deliver_webhook(
    event_id: str,
    webhook_url: str,
    event_type: str,
    payload: Dict[str, Any],
    secret: str = None,
    max_retries: int = 3
):
    """
    Background task to deliver webhooks with retries
    """
    from ...database.connection import SessionLocal
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Skip database updates for test webhooks
    is_test = str(event_id).startswith("test_")
    
    try:
        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": f"EmailTracker-Webhooks/{settings.app_version}",
            "X-EmailTracker-Event": event_type,
            "X-EmailTracker-Delivery-ID": str(event_id)
        }
        
        # Add signature if secret provided
        payload_json = json.dumps(payload, separators=(',', ':'))
        if secret:
            signature = hmac.new(
                secret.encode('utf-8'),
                payload_json.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            headers["X-EmailTracker-Signature"] = f"sha256={signature}"
        
        # Attempt delivery
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                webhook_url,
                content=payload_json,
                headers=headers
            )
            
            success = 200 <= response.status_code < 300
            
            if not is_test:
                # Update database record
                db = SessionLocal()
                try:
                    event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                    if event:
                        event.delivered = success
                        event.delivery_attempts += 1
                        event.last_attempt_at = datetime.utcnow()
                        event.response_status = response.status_code
                        event.response_body = response.text[:1000]  # Limit response body size
                        
                        if not success and event.delivery_attempts < max_retries:
                            # Schedule retry with exponential backoff
                            retry_delay = min(300, 30 * (2 ** event.delivery_attempts))  # Max 5 minutes
                            event.next_attempt_at = datetime.utcnow() + timedelta(seconds=retry_delay)
                        
                        db.commit()
                finally:
                    db.close()
            
            if success:
                logger.info(f"✅ Webhook delivered: {event_type} -> {webhook_url} (HTTP {response.status_code})")
            else:
                logger.warning(f"❌ Webhook failed: {event_type} -> {webhook_url} (HTTP {response.status_code})")
            
    except Exception as e:
        logger.error(f"❌ Webhook delivery error: {event_type} -> {webhook_url} | Error: {str(e)}")
        
        if not is_test:
            # Update database record
            db = SessionLocal()
            try:
                event = db.query(WebhookEvent).filter(WebhookEvent.id == event_id).first()
                if event:
                    event.delivery_attempts += 1
                    event.last_attempt_at = datetime.utcnow()
                    event.response_body = f"Delivery error: {str(e)}"
                    
                    if event.delivery_attempts < max_retries:
                        # Schedule retry
                        retry_delay = min(300, 30 * (2 ** event.delivery_attempts))
                        event.next_attempt_at = datetime.utcnow() + timedelta(seconds=retry_delay)
                    
                    db.commit()
            finally:
                db.close()
