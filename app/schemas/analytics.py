"""
Analytics-related Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class EmailAnalytics(BaseModel):
    """Response schema for email analytics"""
    campaign_id: str = Field(..., description="Campaign ID")
    total_sent: int = Field(..., description="Total emails sent")
    total_delivered: int = Field(..., description="Total emails delivered")
    total_opens: int = Field(..., description="Total email opens")
    total_clicks: int = Field(..., description="Total link clicks")
    total_bounces: int = Field(..., description="Total bounces")
    total_complaints: int = Field(..., description="Total complaints")
    total_unsubscribes: int = Field(..., description="Total unsubscribes")
    
    unique_opens: int = Field(..., description="Unique opens")
    unique_clicks: int = Field(..., description="Unique clicks")
    
    # Rates
    delivery_rate: float = Field(..., description="Delivery rate percentage")
    open_rate: float = Field(..., description="Open rate percentage")
    click_rate: float = Field(..., description="Click rate percentage")
    bounce_rate: float = Field(..., description="Bounce rate percentage")
    complaint_rate: float = Field(..., description="Complaint rate percentage")
    unsubscribe_rate: float = Field(..., description="Unsubscribe rate percentage")
    
    # Time-based data
    created_at: datetime = Field(..., description="Campaign creation time")
    first_sent_at: Optional[datetime] = Field(None, description="First email sent time")
    last_sent_at: Optional[datetime] = Field(None, description="Last email sent time")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "campaign_550e8400-e29b-41d4-a716-446655440001",
                "total_sent": 1000,
                "total_delivered": 980,
                "total_opens": 450,
                "total_clicks": 85,
                "total_bounces": 20,
                "total_complaints": 2,
                "total_unsubscribes": 5,
                "unique_opens": 420,
                "unique_clicks": 75,
                "delivery_rate": 98.0,
                "open_rate": 45.0,
                "click_rate": 8.5,
                "bounce_rate": 2.0,
                "complaint_rate": 0.2,
                "unsubscribe_rate": 0.5,
                "created_at": "2025-01-25T09:00:00Z",
                "first_sent_at": "2025-01-25T10:00:00Z",
                "last_sent_at": "2025-01-25T10:30:00Z"
            }
        }


class DeliverabilityStats(BaseModel):
    """Response schema for overall deliverability statistics"""
    total_sent: int = Field(..., description="Total emails sent across all campaigns")
    delivered: int = Field(..., description="Total emails delivered")
    bounced: int = Field(..., description="Total emails bounced")
    complained: int = Field(..., description="Total complaints received")
    
    delivery_rate: float = Field(..., description="Overall delivery rate percentage")
    bounce_rate: float = Field(..., description="Overall bounce rate percentage")
    complaint_rate: float = Field(..., description="Overall complaint rate percentage")
    
    # Time period
    period_start: Optional[datetime] = Field(None, description="Start of reporting period")
    period_end: Optional[datetime] = Field(None, description="End of reporting period")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_sent": 50000,
                "delivered": 48500,
                "bounced": 1200,
                "complained": 25,
                "delivery_rate": 97.0,
                "bounce_rate": 2.4,
                "complaint_rate": 0.05,
                "period_start": "2025-01-01T00:00:00Z",
                "period_end": "2025-01-25T23:59:59Z"
            }
        }


class EngagementAnalytics(BaseModel):
    """Response schema for engagement analytics"""
    campaign_id: str = Field(..., description="Campaign ID")
    
    # Engagement over time
    opens_by_hour: List[Dict[str, Any]] = Field(..., description="Opens grouped by hour")
    clicks_by_hour: List[Dict[str, Any]] = Field(..., description="Clicks grouped by hour")
    
    # Device breakdown
    opens_by_device: Dict[str, int] = Field(..., description="Opens by device type")
    clicks_by_device: Dict[str, int] = Field(..., description="Clicks by device type")
    
    # Client breakdown
    opens_by_client: Dict[str, int] = Field(..., description="Opens by email client")
    clicks_by_client: Dict[str, int] = Field(..., description="Clicks by email client")
    
    # Geographic breakdown
    opens_by_country: Dict[str, int] = Field(..., description="Opens by country")
    clicks_by_country: Dict[str, int] = Field(..., description="Clicks by country")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "campaign_550e8400-e29b-41d4-a716-446655440001",
                "opens_by_hour": [
                    {"hour": "2025-01-25T10:00:00Z", "count": 45},
                    {"hour": "2025-01-25T11:00:00Z", "count": 32}
                ],
                "clicks_by_hour": [
                    {"hour": "2025-01-25T10:00:00Z", "count": 8},
                    {"hour": "2025-01-25T11:00:00Z", "count": 5}
                ],
                "opens_by_device": {"desktop": 250, "mobile": 150, "tablet": 50},
                "clicks_by_device": {"desktop": 45, "mobile": 25, "tablet": 15},
                "opens_by_client": {"Gmail": 200, "Outlook": 150, "Apple Mail": 100},
                "clicks_by_client": {"Gmail": 35, "Outlook": 30, "Apple Mail": 20},
                "opens_by_country": {"United States": 200, "Canada": 100, "United Kingdom": 150},
                "clicks_by_country": {"United States": 35, "Canada": 20, "United Kingdom": 30}
            }
        }


class TopPerformingLinks(BaseModel):
    """Response schema for top performing links in a campaign"""
    campaign_id: str = Field(..., description="Campaign ID")
    links: List[Dict[str, Any]] = Field(..., description="Top performing links with click counts")
    total_clicks: int = Field(..., description="Total clicks across all links")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": "campaign_550e8400-e29b-41d4-a716-446655440001",
                "links": [
                    {"url": "https://example.com/product1", "clicks": 45, "unique_clicks": 42},
                    {"url": "https://example.com/product2", "clicks": 32, "unique_clicks": 30},
                    {"url": "https://example.com/unsubscribe", "clicks": 8, "unique_clicks": 8}
                ],
                "total_clicks": 85
            }
        }
