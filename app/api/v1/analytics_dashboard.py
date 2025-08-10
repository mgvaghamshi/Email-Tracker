"""
New Analytics Dashboard endpoint with flattened structure for frontend
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.models import Campaign, EmailTracker, EmailEvent, Contact
from ...database.user_models import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard")
async def get_dashboard_analytics(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard analytics with flattened structure for frontend
    
    Returns overall analytics, recent campaigns, and all metrics in frontend-expected format
    """
    try:
        # Get all campaigns for this user
        campaigns = db.query(Campaign).filter(Campaign.user_id == current_user.id).all()
        campaign_ids = [c.id for c in campaigns] if campaigns else []
        
        if not campaign_ids:
            return {
                "total_campaigns": 0,
                "total_emails_sent": 0,
                "total_delivered": 0,
                "total_opened": 0,
                "total_clicked": 0,
                "total_bounced": 0,
                "total_unsubscribed": 0,
                "total_opens": 0,  # Total opens (including repeated)
                "total_clicks": 0, # Total clicks (including repeated)
                "overall_open_rate": 0.0,
                "overall_click_rate": 0.0,
                "overall_bounce_rate": 0.0,
                "overall_unsubscribe_rate": 0.0,
                "recent_campaigns": []
            }
        
        # Get all email trackers for user's campaigns
        email_trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id.in_(campaign_ids)
        ).all()
        
        # Calculate overall metrics
        total_campaigns = len(campaigns)
        total_emails_sent = len(email_trackers)
        total_delivered = sum(1 for t in email_trackers if t.delivered)
        total_opened = sum(1 for t in email_trackers if t.opened_at is not None)  # Unique opens
        total_clicked = sum(1 for t in email_trackers if t.click_count > 0)  # Unique clicks
        total_bounced = sum(1 for t in email_trackers if t.bounced)
        total_unsubscribed = sum(1 for t in email_trackers if t.unsubscribed)
        
        # Total opens and clicks (including repeated)
        total_opens = sum(t.open_count for t in email_trackers if t.open_count)
        total_clicks = sum(t.click_count for t in email_trackers if t.click_count)
        
        # Calculate rates
        overall_open_rate = (total_opened / total_delivered * 100) if total_delivered > 0 else 0.0
        overall_click_rate = (total_clicked / total_delivered * 100) if total_delivered > 0 else 0.0
        overall_bounce_rate = (total_bounced / total_emails_sent * 100) if total_emails_sent > 0 else 0.0
        overall_unsubscribe_rate = (total_unsubscribed / total_delivered * 100) if total_delivered > 0 else 0.0
        
        # Get recent campaigns (last 10) with their stats
        recent_campaigns = db.query(Campaign).filter(
            Campaign.user_id == current_user.id
        ).order_by(Campaign.created_at.desc()).limit(10).all()
        
        recent_campaign_data = []
        for campaign in recent_campaigns:
            # Get campaign stats
            campaign_trackers = [t for t in email_trackers if t.campaign_id == campaign.id]
            
            if campaign_trackers:
                campaign_delivered = sum(1 for t in campaign_trackers if t.delivered)
                campaign_opened = sum(1 for t in campaign_trackers if t.opened_at is not None)
                campaign_clicked = sum(1 for t in campaign_trackers if t.click_count > 0)
                
                campaign_open_rate = (campaign_opened / campaign_delivered * 100) if campaign_delivered > 0 else 0.0
                campaign_click_rate = (campaign_clicked / campaign_delivered * 100) if campaign_delivered > 0 else 0.0
                emails_sent = campaign_delivered
            else:
                campaign_open_rate = 0.0
                campaign_click_rate = 0.0
                emails_sent = 0
            
            recent_campaign_data.append({
                "id": campaign.id,
                "name": campaign.name,
                "status": campaign.status,
                "created_at": campaign.created_at.isoformat(),
                "emails_sent": emails_sent,
                "open_rate": round(campaign_open_rate, 2),
                "click_rate": round(campaign_click_rate, 2)
            })
        
        return {
            "total_campaigns": total_campaigns,
            "total_emails_sent": total_emails_sent,
            "total_delivered": total_delivered,
            "total_opened": total_opened,
            "total_clicked": total_clicked,
            "total_bounced": total_bounced,
            "total_unsubscribed": total_unsubscribed,
            "total_opens": total_opens,
            "total_clicks": total_clicks,
            "overall_open_rate": round(overall_open_rate, 2),
            "overall_click_rate": round(overall_click_rate, 2),
            "overall_bounce_rate": round(overall_bounce_rate, 2),
            "overall_unsubscribe_rate": round(overall_unsubscribe_rate, 2),
            "recent_campaigns": recent_campaign_data
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get dashboard analytics: {str(e)}"
        )


@router.get("/deliverability")
async def get_deliverability_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in stats"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive deliverability statistics including inbox rate, spam rate, and reputation score
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Get user's campaigns
        user_campaigns = db.query(Campaign).filter(Campaign.user_id == current_user.id).all()
        campaign_ids = [c.id for c in user_campaigns]
        
        if not campaign_ids:
            return {
                "inbox_rate": 0.0,
                "spam_rate": 0.0,
                "bounce_rate": 0.0,
                "reputation_score": 100,  # Default good score when no data
                "total_sent": 0,
                "delivered": 0,
                "bounced": 0,
                "complained": 0,
                "delivery_rate": 0.0,
                "complaint_rate": 0.0,
                "period_start": start_date,
                "period_end": end_date
            }
        
        # Get trackers within date range for user's campaigns
        trackers = db.query(EmailTracker).filter(
            EmailTracker.campaign_id.in_(campaign_ids),
            EmailTracker.created_at >= start_date,
            EmailTracker.created_at <= end_date
        ).all()
        
        # Calculate basic metrics
        total_sent = len(trackers)
        delivered = sum(1 for t in trackers if t.delivered)
        bounced = sum(1 for t in trackers if t.bounced)
        complained = sum(1 for t in trackers if t.complained)
        
        # Calculate rates
        delivery_rate = (delivered / total_sent * 100) if total_sent > 0 else 0
        bounce_rate = (bounced / total_sent * 100) if total_sent > 0 else 0
        complaint_rate = (complained / total_sent * 100) if total_sent > 0 else 0
        
        # Calculate advanced deliverability metrics
        # Inbox Rate: Estimate based on delivered emails that were opened (rough proxy)
        opened_emails = sum(1 for t in trackers if t.opened_at is not None)
        inbox_rate = (opened_emails / delivered * 80) if delivered > 0 else 0  # Rough estimate: opened emails likely reached inbox
        inbox_rate = min(inbox_rate, 100.0)  # Cap at 100%
        
        # Spam Rate: Estimate based on delivered but not opened + complaints
        unread_delivered = delivered - opened_emails
        estimated_spam = min(unread_delivered * 0.3, delivered * 0.2)  # Conservative estimate
        spam_rate = ((estimated_spam + complained) / total_sent * 100) if total_sent > 0 else 0
        spam_rate = min(spam_rate, 100.0)  # Cap at 100%
        
        # Reputation Score: Calculate based on multiple factors (0-100)
        reputation_score = 100
        
        # Penalize for high bounce rate
        if bounce_rate > 5:
            reputation_score -= min((bounce_rate - 5) * 2, 30)
        
        # Penalize for high complaint rate
        if complaint_rate > 0.1:
            reputation_score -= min((complaint_rate - 0.1) * 100, 40)
        
        # Penalize for low delivery rate
        if delivery_rate < 95:
            reputation_score -= min((95 - delivery_rate) * 2, 20)
        
        # Reward for good inbox rate
        if inbox_rate > 80:
            reputation_score = min(reputation_score + 5, 100)
        
        reputation_score = max(reputation_score, 0)  # Minimum 0
        
        return {
            "inbox_rate": round(inbox_rate, 1),
            "spam_rate": round(spam_rate, 1),
            "bounce_rate": round(bounce_rate, 2),
            "reputation_score": round(reputation_score),
            "total_sent": total_sent,
            "delivered": delivered,
            "bounced": bounced,
            "complained": complained,
            "delivery_rate": round(delivery_rate, 2),
            "complaint_rate": round(complaint_rate, 2),
            "period_start": start_date,
            "period_end": end_date
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get deliverability stats: {str(e)}"
        )


@router.get("/summary")
async def get_analytics_summary(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
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
        # Calculate 24-hour period
        now = datetime.utcnow()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # Get user's campaigns
        campaigns = db.query(Campaign).filter(Campaign.user_id == current_user.id).all()
        campaign_ids = [c.id for c in campaigns] if campaigns else []
        
        if not campaign_ids:
            return {
                "emails_last_24h": 0,
                "opens_last_24h": 0,
                "clicks_last_24h": 0,
                "active_campaigns": 0
            }
        
        # Count active campaigns
        active_campaigns = db.query(Campaign).filter(
            Campaign.user_id == current_user.id,
            Campaign.status.in_(['sending', 'scheduled', 'active'])
        ).count()
        
        # Get email statistics for the last 24 hours
        email_trackers_24h = db.query(EmailTracker).filter(
            EmailTracker.campaign_id.in_(campaign_ids),
            EmailTracker.created_at >= twenty_four_hours_ago
        ).all()
        
        # Count emails sent in last 24 hours
        emails_last_24h = len(email_trackers_24h)
        
        # Count opens in last 24 hours (emails with opened_at within 24h)
        opens_last_24h = len([
            tracker for tracker in email_trackers_24h 
            if tracker.opened_at and tracker.opened_at >= twenty_four_hours_ago
        ])
        
        # Count clicks in last 24 hours (emails with click_count > 0 and first_click_at within 24h)
        clicks_last_24h = len([
            tracker for tracker in email_trackers_24h 
            if tracker.click_count > 0 and tracker.first_click_at and tracker.first_click_at >= twenty_four_hours_ago
        ])
        
        return {
            "emails_last_24h": emails_last_24h,
            "opens_last_24h": opens_last_24h,
            "clicks_last_24h": clicks_last_24h,
            "active_campaigns": active_campaigns
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get analytics summary: {str(e)}"
        )
