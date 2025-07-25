"""
Analytics and reporting endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ...dependencies import get_db, get_api_key
from ...database.models import EmailTracker, EmailEvent, EmailClick, EmailBounce
from ...schemas.analytics import (
    EmailAnalytics, DeliverabilityStats, EngagementAnalytics, TopPerformingLinks
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/campaigns/{campaign_id}", response_model=EmailAnalytics)
async def get_campaign_analytics(
    campaign_id: str,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> EmailAnalytics:
    """
    Get comprehensive analytics for a specific campaign
    
    Returns detailed engagement metrics, delivery statistics, and performance
    indicators for all emails in a campaign.
    
    **Path Parameters:**
    - **campaign_id**: Unique campaign identifier
    
    **Metrics Included:**
    - Total emails sent, delivered, opened, clicked
    - Bounce and complaint counts
    - Engagement rates (open rate, click rate, etc.)
    - Campaign timing information
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/campaigns/newsletter-january-2025"
    ```
    """
    try:
        # Get all trackers for this campaign
        trackers = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id).all()
        
        if not trackers:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        # Calculate basic metrics
        total_sent = len(trackers)
        total_delivered = sum(1 for t in trackers if t.delivered)
        total_opens = sum(1 for t in trackers if t.opened_at)
        total_clicks = sum(t.click_count for t in trackers)
        total_bounces = sum(1 for t in trackers if t.bounced)
        total_complaints = sum(1 for t in trackers if t.complained)
        total_unsubscribes = sum(1 for t in trackers if t.unsubscribed)
        
        # Calculate unique metrics
        unique_opens = sum(t.unique_opens for t in trackers if t.unique_opens)
        unique_clicks = sum(t.unique_clicks for t in trackers if t.unique_clicks)
        
        # Calculate rates
        delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
        open_rate = (total_opens / total_delivered * 100) if total_delivered > 0 else 0
        click_rate = (total_clicks / total_delivered * 100) if total_delivered > 0 else 0
        bounce_rate = (total_bounces / total_sent * 100) if total_sent > 0 else 0
        complaint_rate = (total_complaints / total_delivered * 100) if total_delivered > 0 else 0
        unsubscribe_rate = (total_unsubscribes / total_delivered * 100) if total_delivered > 0 else 0
        
        # Get timing information
        creation_times = [t.created_at for t in trackers]
        sent_times = [t.sent_at for t in trackers if t.sent_at]
        
        created_at = min(creation_times) if creation_times else datetime.utcnow()
        first_sent_at = min(sent_times) if sent_times else None
        last_sent_at = max(sent_times) if sent_times else None
        
        return EmailAnalytics(
            campaign_id=campaign_id,
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_opens=total_opens,
            total_clicks=total_clicks,
            total_bounces=total_bounces,
            total_complaints=total_complaints,
            total_unsubscribes=total_unsubscribes,
            unique_opens=unique_opens,
            unique_clicks=unique_clicks,
            delivery_rate=round(delivery_rate, 2),
            open_rate=round(open_rate, 2),
            click_rate=round(click_rate, 2),
            bounce_rate=round(bounce_rate, 2),
            complaint_rate=round(complaint_rate, 2),
            unsubscribe_rate=round(unsubscribe_rate, 2),
            created_at=created_at,
            first_sent_at=first_sent_at,
            last_sent_at=last_sent_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get campaign analytics: {str(e)}"
        )


@router.get("/deliverability", response_model=DeliverabilityStats)
async def get_deliverability_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> DeliverabilityStats:
    """
    Get overall deliverability statistics
    
    Returns high-level deliverability metrics across all campaigns within
    the specified time period.
    
    **Query Parameters:**
    - **days**: Number of days to include in statistics (1-365, default: 30)
    
    **Metrics Included:**
    - Total emails sent and delivered
    - Bounce and complaint rates
    - Overall delivery performance
    
    **Example Usage:**
    ```bash
    # Get last 30 days
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/deliverability"
         
    # Get last 7 days
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/deliverability?days=7"
    ```
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get trackers within date range
        trackers = db.query(EmailTracker).filter(
            EmailTracker.created_at >= start_date,
            EmailTracker.created_at <= end_date
        ).all()
        
        # Calculate metrics
        total_sent = len(trackers)
        delivered = sum(1 for t in trackers if t.delivered)
        bounced = sum(1 for t in trackers if t.bounced)
        complained = sum(1 for t in trackers if t.complained)
        
        # Calculate rates
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
        complaint_rate = (complained / total_sent * 100) if total_sent > 0 else 0
        
        return DeliverabilityStats(
            total_sent=total_sent,
            delivered=delivered,
            bounced=bounced,
            complained=complained,
            delivery_rate=round(delivery_rate, 2),
            bounce_rate=round(bounce_rate, 2),
            complaint_rate=round(complaint_rate, 2),
            period_start=start_date,
            period_end=end_date
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deliverability stats: {str(e)}"
        )


@router.get("/campaigns/{campaign_id}/engagement", response_model=EngagementAnalytics)
async def get_campaign_engagement(
    campaign_id: str,
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> EngagementAnalytics:
    """
    Get detailed engagement analytics for a campaign
    
    Returns comprehensive engagement breakdowns including device types,
    email clients, geographic data, and temporal patterns.
    
    **Path Parameters:**
    - **campaign_id**: Unique campaign identifier
    
    **Analytics Included:**
    - Hourly engagement patterns
    - Device and client breakdowns
    - Geographic distribution
    - User behavior insights
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/campaigns/newsletter-january-2025/engagement"
    ```
    """
    try:
        # Verify campaign exists
        trackers = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id).all()
        if not trackers:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        tracker_ids = [t.id for t in trackers]
        
        # Get all events for this campaign
        events = db.query(EmailEvent).filter(
            EmailEvent.tracker_id.in_(tracker_ids),
            EmailEvent.is_bot == False  # Exclude bot events
        ).all()
        
        # Initialize analytics data
        opens_by_hour = {}
        clicks_by_hour = {}
        opens_by_device = {}
        clicks_by_device = {}
        opens_by_client = {}
        clicks_by_client = {}
        opens_by_country = {}
        clicks_by_country = {}
        
        # Process events
        for event in events:
            # Group by hour
            hour_key = event.timestamp.strftime("%Y-%m-%dT%H:00:00Z")
            
            if event.event_type == "open":
                opens_by_hour[hour_key] = opens_by_hour.get(hour_key, 0) + 1
                if event.device_type:
                    opens_by_device[event.device_type] = opens_by_device.get(event.device_type, 0) + 1
                if event.client_name:
                    opens_by_client[event.client_name] = opens_by_client.get(event.client_name, 0) + 1
                if event.country:
                    opens_by_country[event.country] = opens_by_country.get(event.country, 0) + 1
                    
            elif event.event_type == "click":
                clicks_by_hour[hour_key] = clicks_by_hour.get(hour_key, 0) + 1
                if event.device_type:
                    clicks_by_device[event.device_type] = clicks_by_device.get(event.device_type, 0) + 1
                if event.client_name:
                    clicks_by_client[event.client_name] = clicks_by_client.get(event.client_name, 0) + 1
                if event.country:
                    clicks_by_country[event.country] = clicks_by_country.get(event.country, 0) + 1
        
        # Convert to list format for hourly data
        opens_by_hour_list = [{"hour": k, "count": v} for k, v in sorted(opens_by_hour.items())]
        clicks_by_hour_list = [{"hour": k, "count": v} for k, v in sorted(clicks_by_hour.items())]
        
        return EngagementAnalytics(
            campaign_id=campaign_id,
            opens_by_hour=opens_by_hour_list,
            clicks_by_hour=clicks_by_hour_list,
            opens_by_device=opens_by_device,
            clicks_by_device=clicks_by_device,
            opens_by_client=opens_by_client,
            clicks_by_client=clicks_by_client,
            opens_by_country=opens_by_country,
            clicks_by_country=clicks_by_country
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get engagement analytics: {str(e)}"
        )


@router.get("/campaigns/{campaign_id}/top-links", response_model=TopPerformingLinks)
async def get_top_performing_links(
    campaign_id: str,
    limit: int = Query(10, ge=1, le=100, description="Number of top links to return"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> TopPerformingLinks:
    """
    Get top performing links in a campaign
    
    Returns the most clicked links in a campaign, ranked by click count.
    
    **Path Parameters:**
    - **campaign_id**: Unique campaign identifier
    
    **Query Parameters:**
    - **limit**: Number of top links to return (1-100, default: 10)
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/campaigns/newsletter-january-2025/top-links"
    ```
    """
    try:
        # Verify campaign exists
        trackers = db.query(EmailTracker).filter(EmailTracker.campaign_id == campaign_id).all()
        if not trackers:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        tracker_ids = [t.id for t in trackers]
        
        # Get click statistics by URL
        click_stats = db.query(
            EmailClick.url,
            func.count(EmailClick.id).label('total_clicks'),
            func.count(func.distinct(EmailClick.ip_address)).label('unique_clicks')
        ).filter(
            EmailClick.tracker_id.in_(tracker_ids)
        ).group_by(
            EmailClick.url
        ).order_by(
            func.count(EmailClick.id).desc()
        ).limit(limit).all()
        
        # Format results
        links = []
        total_clicks = 0
        
        for url, clicks, unique_clicks in click_stats:
            links.append({
                "url": url,
                "clicks": clicks,
                "unique_clicks": unique_clicks
            })
            total_clicks += clicks
        
        return TopPerformingLinks(
            campaign_id=campaign_id,
            links=links,
            total_clicks=total_clicks
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get top performing links: {str(e)}"
        )


@router.get("/summary")
async def get_analytics_summary(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    api_key: str = Depends(get_api_key),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a summary of key analytics metrics
    
    Returns a high-level dashboard summary of your email performance
    over the specified time period.
    
    **Query Parameters:**
    - **days**: Number of days to include (1-365, default: 30)
    
    **Example Usage:**
    ```bash
    curl -H "Authorization: Bearer your_api_key" \\
         "https://api.emailtracker.com/api/v1/analytics/summary"
    ```
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get basic counts
        total_campaigns = db.query(func.count(func.distinct(EmailTracker.campaign_id))).filter(
            EmailTracker.created_at >= start_date
        ).scalar()
        
        total_emails = db.query(func.count(EmailTracker.id)).filter(
            EmailTracker.created_at >= start_date
        ).scalar()
        
        delivered_emails = db.query(func.count(EmailTracker.id)).filter(
            EmailTracker.created_at >= start_date,
            EmailTracker.delivered == True
        ).scalar()
        
        opened_emails = db.query(func.count(EmailTracker.id)).filter(
            EmailTracker.created_at >= start_date,
            EmailTracker.opened_at.isnot(None)
        ).scalar()
        
        # Get event counts
        total_clicks = db.query(func.count(EmailClick.id)).join(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        ).scalar()
        
        # Calculate rates
        delivery_rate = (delivered_emails / total_emails * 100) if total_emails > 0 else 0
        open_rate = (opened_emails / delivered_emails * 100) if delivered_emails > 0 else 0
        click_rate = (total_clicks / delivered_emails * 100) if delivered_emails > 0 else 0
        
        return {
            "period": {
                "days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "campaigns": {
                "total": total_campaigns
            },
            "emails": {
                "sent": total_emails,
                "delivered": delivered_emails,
                "opened": opened_emails,
                "delivery_rate": round(delivery_rate, 2),
                "open_rate": round(open_rate, 2)
            },
            "engagement": {
                "total_clicks": total_clicks,
                "click_rate": round(click_rate, 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics summary: {str(e)}"
        )
