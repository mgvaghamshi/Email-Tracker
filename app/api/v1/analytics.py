"""
Analytics API Endpoints
Handles all analytics-related operations including dashboard stats, deliverability metrics, and summaries
"""
from fastapi import APIRouter, HTTPException, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging

from ...db import SessionLocal
from ...models import EmailCampaign, EmailTracker, EmailEvent, EmailBounce, EmailClick
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============= Pydantic Schemas =============

class AnalyticsSummary(BaseModel):
    """Schema for 24-hour analytics summary"""
    emails_last_24h: int
    opens_last_24h: int
    clicks_last_24h: int
    active_campaigns: int


class CampaignSummary(BaseModel):
    """Schema for campaign summary in dashboard"""
    id: str
    name: str
    total_sent: int
    total_opens: int
    total_clicks: int
    open_rate: float
    click_rate: float
    created_at: datetime


class DashboardAnalytics(BaseModel):
    """Schema for comprehensive dashboard analytics"""
    # Overall metrics
    total_emails_sent: int
    total_campaigns: int
    total_opens: int
    total_clicks: int
    total_bounces: int
    
    # Rates
    overall_open_rate: float
    overall_click_rate: float
    overall_bounce_rate: float
    
    # Recent activity (last 7 days)
    recent_emails_sent: int
    recent_opens: int
    recent_clicks: int
    
    # Recent campaigns
    recent_campaigns: List[CampaignSummary]
    
    # Top performing
    top_campaign: Optional[Dict[str, Any]] = None


class DeliverabilityStats(BaseModel):
    """Schema for deliverability statistics"""
    total_sent: int
    total_delivered: int
    total_bounced: int
    total_failed: int
    
    # Rates
    delivery_rate: float
    bounce_rate: float
    
    # Bounce breakdown
    hard_bounces: int
    soft_bounces: int
    
    # Reputation metrics
    inbox_rate: float = Field(description="Estimated inbox placement rate")
    spam_rate: float = Field(description="Estimated spam folder rate")
    reputation_score: float = Field(ge=0, le=100, description="Overall sender reputation score")
    
    # Time period
    period_days: int


class EngagementMetrics(BaseModel):
    """Schema for engagement metrics"""
    total_opens: int
    total_clicks: int
    unique_opens: int
    unique_clicks: int
    open_rate: float
    click_rate: float
    click_to_open_rate: float


# ============= Utility Functions =============

def calculate_rate(numerator: int, denominator: int) -> float:
    """Calculate percentage rate"""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def calculate_reputation_score(delivery_rate: float, bounce_rate: float, open_rate: float) -> float:
    """Calculate sender reputation score (0-100)"""
    # Weight factors: delivery (40%), low bounce (30%), opens (30%)
    delivery_score = delivery_rate * 0.4
    bounce_score = (100 - bounce_rate) * 0.3
    engagement_score = open_rate * 0.3
    
    return round(delivery_score + bounce_score + engagement_score, 2)


# ============= API Endpoints =============

@router.get("/dashboard")
async def get_dashboard_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive dashboard analytics with flattened structure for frontend
    
    Returns overall analytics, recent campaigns, and all metrics in frontend-expected format
    """
    try:
        # Calculate date ranges
        now = datetime.utcnow()
        seven_days_ago = now - timedelta(days=7)
        
        # Get all active campaigns
        all_campaigns = db.query(EmailCampaign).filter(
            EmailCampaign.is_active == True
        ).all()
        
        total_campaigns = len(all_campaigns)
        
        # Get all email trackers
        all_trackers = db.query(EmailTracker).all()
        total_emails_sent = len(all_trackers)
        
        # Count opens and clicks
        total_opens = sum(1 for t in all_trackers if t.opened_at)
        total_clicks = sum(t.click_count for t in all_trackers)
        
        # Count bounces
        total_bounces = db.query(EmailBounce).count()
        
        # Calculate overall rates
        overall_open_rate = calculate_rate(total_opens, total_emails_sent)
        overall_click_rate = calculate_rate(total_clicks, total_emails_sent)
        overall_bounce_rate = calculate_rate(total_bounces, total_emails_sent)
        
        # Recent activity (last 7 days)
        recent_trackers = [t for t in all_trackers if t.created_at and t.created_at > seven_days_ago]
        recent_emails_sent = len(recent_trackers)
        recent_opens = sum(1 for t in recent_trackers if t.opened_at and t.opened_at > seven_days_ago)
        recent_clicks = sum(1 for t in recent_trackers if t.click_count > 0)
        
        # Get recent campaigns (last 10)
        recent_campaign_list = db.query(EmailCampaign).filter(
            EmailCampaign.is_active == True
        ).order_by(desc(EmailCampaign.created_at)).limit(10).all()
        
        recent_campaigns = []
        for campaign in recent_campaign_list:
            campaign_trackers = [t for t in all_trackers if t.campaign_id == campaign.id]
            campaign_sent = len(campaign_trackers)
            campaign_opens = sum(1 for t in campaign_trackers if t.opened_at)
            campaign_clicks = sum(t.click_count for t in campaign_trackers)
            
            recent_campaigns.append(CampaignSummary(
                id=campaign.id,
                name=campaign.name,
                total_sent=campaign_sent,
                total_opens=campaign_opens,
                total_clicks=campaign_clicks,
                open_rate=calculate_rate(campaign_opens, campaign_sent),
                click_rate=calculate_rate(campaign_clicks, campaign_sent),
                created_at=campaign.created_at
            ))
        
        # Find top performing campaign
        top_campaign = None
        if all_campaigns:
            best_campaign = max(all_campaigns, key=lambda c: c.open_rate if hasattr(c, 'open_rate') else 0)
            campaign_trackers = [t for t in all_trackers if t.campaign_id == best_campaign.id]
            
            if campaign_trackers:
                top_campaign = {
                    "id": best_campaign.id,
                    "name": best_campaign.name,
                    "open_rate": best_campaign.open_rate if hasattr(best_campaign, 'open_rate') else calculate_rate(
                        sum(1 for t in campaign_trackers if t.opened_at),
                        len(campaign_trackers)
                    )
                }
        
        return DashboardAnalytics(
            total_emails_sent=total_emails_sent,
            total_campaigns=total_campaigns,
            total_opens=total_opens,
            total_clicks=total_clicks,
            total_bounces=total_bounces,
            overall_open_rate=overall_open_rate,
            overall_click_rate=overall_click_rate,
            overall_bounce_rate=overall_bounce_rate,
            recent_emails_sent=recent_emails_sent,
            recent_opens=recent_opens,
            recent_clicks=recent_clicks,
            recent_campaigns=recent_campaigns,
            top_campaign=top_campaign
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard analytics: {str(e)}"
        )


@router.get("/deliverability")
async def get_deliverability_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get comprehensive deliverability statistics including inbox rate, spam rate, and reputation score
    """
    try:
        # Calculate date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get trackers in the time period
        trackers_query = db.query(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        )
        
        all_trackers = trackers_query.all()
        total_sent = len(all_trackers)
        
        # Count delivered emails
        total_delivered = sum(1 for t in all_trackers if t.delivered)
        
        # Get bounces
        bounces = db.query(EmailBounce).join(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        ).all()
        
        total_bounced = len(bounces)
        total_failed = total_sent - total_delivered
        
        # Bounce breakdown
        hard_bounces = sum(1 for b in bounces if b.bounce_type == 'hard')
        soft_bounces = sum(1 for b in bounces if b.bounce_type == 'soft')
        
        # Calculate rates
        delivery_rate = calculate_rate(total_delivered, total_sent)
        bounce_rate = calculate_rate(total_bounced, total_sent)
        
        # Calculate opens for engagement
        total_opens = sum(1 for t in all_trackers if t.opened_at)
        open_rate = calculate_rate(total_opens, total_delivered if total_delivered > 0 else total_sent)
        
        # Estimate inbox vs spam placement
        # If emails are opened, they likely reached the inbox
        # High open rate = high inbox rate
        inbox_rate = min(open_rate * 1.2, 100.0)  # Approximate: opened emails + some unopened in inbox
        spam_rate = max(0.0, 100.0 - inbox_rate - bounce_rate)
        
        # Calculate reputation score
        reputation_score = calculate_reputation_score(delivery_rate, bounce_rate, open_rate)
        
        return DeliverabilityStats(
            total_sent=total_sent,
            total_delivered=total_delivered,
            total_bounced=total_bounced,
            total_failed=total_failed,
            delivery_rate=delivery_rate,
            bounce_rate=bounce_rate,
            hard_bounces=hard_bounces,
            soft_bounces=soft_bounces,
            inbox_rate=inbox_rate,
            spam_rate=spam_rate,
            reputation_score=reputation_score,
            period_days=days
        )
        
    except Exception as e:
        logger.error(f"Error getting deliverability stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting deliverability stats: {str(e)}"
        )


@router.get("/summary")
async def get_analytics_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get 24-hour analytics summary for the authenticated user
    
    Returns:
    - emails_last_24h: Number of emails sent in the last 24 hours
    - opens_last_24h: Number of opens in the last 24 hours
    - clicks_last_24h: Number of clicks in the last 24 hours
    - active_campaigns: Number of active campaigns
    """
    try:
        # Calculate time range
        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # Get emails sent in last 24 hours
        recent_trackers = db.query(EmailTracker).filter(
            EmailTracker.created_at >= twenty_four_hours_ago
        ).all()
        
        emails_last_24h = len(recent_trackers)
        
        # Count opens in last 24 hours
        opens_last_24h = sum(
            1 for t in recent_trackers 
            if t.opened_at and t.opened_at >= twenty_four_hours_ago
        )
        
        # Count clicks in last 24 hours
        clicks_last_24h = db.query(EmailClick).filter(
            EmailClick.timestamp >= twenty_four_hours_ago
        ).count()
        
        # Count active campaigns
        active_campaigns = db.query(EmailCampaign).filter(
            EmailCampaign.is_active == True
        ).count()
        
        return AnalyticsSummary(
            emails_last_24h=emails_last_24h,
            opens_last_24h=opens_last_24h,
            clicks_last_24h=clicks_last_24h,
            active_campaigns=active_campaigns
        )
        
    except Exception as e:
        logger.error(f"Error getting analytics summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting analytics summary: {str(e)}"
        )


@router.get("/campaigns/{campaign_id}")
async def get_campaign_analytics(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific campaign
    """
    try:
        # Get campaign
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id,
            EmailCampaign.is_active == True
        ).first()
        
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Get all trackers for this campaign
        trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).all()
        
        total_sent = len(trackers)
        total_delivered = sum(1 for t in trackers if t.delivered)
        
        # Count opens
        opened_trackers = [t for t in trackers if t.opened_at]
        total_opens = len(opened_trackers)
        unique_opens = total_opens  # In this simple model, each tracker represents one recipient
        
        # Count clicks
        total_clicks = sum(t.click_count for t in trackers)
        clicked_trackers = [t for t in trackers if t.click_count > 0]
        unique_clicks = len(clicked_trackers)
        
        # Get bounces
        bounces = db.query(EmailBounce).join(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).all()
        total_bounces = len(bounces)
        
        # Calculate rates
        open_rate = calculate_rate(total_opens, total_sent)
        click_rate = calculate_rate(total_clicks, total_sent)
        bounce_rate = calculate_rate(total_bounces, total_sent)
        click_to_open_rate = calculate_rate(unique_clicks, unique_opens)
        
        # Get events
        events = db.query(EmailEvent).join(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).order_by(desc(EmailEvent.timestamp)).limit(50).all()
        
        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.name,
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_opens": total_opens,
            "unique_opens": unique_opens,
            "total_clicks": total_clicks,
            "unique_clicks": unique_clicks,
            "total_bounces": total_bounces,
            "open_rate": open_rate,
            "click_rate": click_rate,
            "bounce_rate": bounce_rate,
            "click_to_open_rate": click_to_open_rate,
            "engagement_metrics": EngagementMetrics(
                total_opens=total_opens,
                total_clicks=total_clicks,
                unique_opens=unique_opens,
                unique_clicks=unique_clicks,
                open_rate=open_rate,
                click_rate=click_rate,
                click_to_open_rate=click_to_open_rate
            ),
            "recent_events": [
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "timestamp": event.timestamp,
                    "user_agent": event.user_agent,
                    "ip_address": event.ip_address
                }
                for event in events
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting campaign analytics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting campaign analytics: {str(e)}"
        )


@router.get("/engagement")
async def get_engagement_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get engagement metrics for a time period
    """
    try:
        # Calculate date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get trackers in the time period
        trackers = db.query(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        ).all()
        
        total_sent = len(trackers)
        
        # Count opens
        opened_trackers = [t for t in trackers if t.opened_at]
        total_opens = sum(t.open_count for t in trackers)
        unique_opens = len(opened_trackers)
        
        # Count clicks
        total_clicks = sum(t.click_count for t in trackers)
        clicked_trackers = [t for t in trackers if t.click_count > 0]
        unique_clicks = len(clicked_trackers)
        
        # Calculate rates
        open_rate = calculate_rate(unique_opens, total_sent)
        click_rate = calculate_rate(unique_clicks, total_sent)
        click_to_open_rate = calculate_rate(unique_clicks, unique_opens)
        
        return EngagementMetrics(
            total_opens=total_opens,
            total_clicks=total_clicks,
            unique_opens=unique_opens,
            unique_clicks=unique_clicks,
            open_rate=open_rate,
            click_rate=click_rate,
            click_to_open_rate=click_to_open_rate
        )
        
    except Exception as e:
        logger.error(f"Error getting engagement metrics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting engagement metrics: {str(e)}"
        )


@router.get("/trends")
async def get_analytics_trends(
    days: int = Query(30, ge=7, le=365, description="Number of days for trend analysis"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get analytics trends over time (daily breakdown)
    """
    try:
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get all trackers in the time period
        trackers = db.query(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        ).all()
        
        # Group by day
        daily_stats = {}
        
        for i in range(days + 1):
            current_day = start_date + timedelta(days=i)
            day_key = current_day.strftime('%Y-%m-%d')
            daily_stats[day_key] = {
                "date": day_key,
                "emails_sent": 0,
                "opens": 0,
                "clicks": 0,
                "bounces": 0
            }
        
        # Aggregate tracker data by day
        for tracker in trackers:
            if tracker.created_at:
                day_key = tracker.created_at.strftime('%Y-%m-%d')
                if day_key in daily_stats:
                    daily_stats[day_key]["emails_sent"] += 1
                    if tracker.opened_at:
                        daily_stats[day_key]["opens"] += 1
                    daily_stats[day_key]["clicks"] += tracker.click_count
        
        # Get bounces
        bounces = db.query(EmailBounce).join(EmailTracker).filter(
            EmailTracker.created_at >= start_date
        ).all()
        
        for bounce in bounces:
            if bounce.timestamp:
                day_key = bounce.timestamp.strftime('%Y-%m-%d')
                if day_key in daily_stats:
                    daily_stats[day_key]["bounces"] += 1
        
        # Convert to list and sort by date
        trends = sorted(daily_stats.values(), key=lambda x: x["date"])
        
        return {
            "period_days": days,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily_trends": trends
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting analytics trends: {str(e)}"
        )
