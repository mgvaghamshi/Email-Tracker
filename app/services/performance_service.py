"""
High-performance service layer for common database operations
"""
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_, or_
from sqlalchemy.dialects import sqlite, postgresql
import json

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from ..database.models import EmailTracker, Campaign, EmailEvent
from ..config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Redis cache service with fallback"""
    
    def __init__(self):
        self.redis_client = None
        if REDIS_AVAILABLE and hasattr(settings, 'redis_url'):
            try:
                self.redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                self.redis_client.ping()  # Test connection
                logger.info("Redis cache enabled")
            except Exception as e:
                logger.warning(f"Redis not available: {e}")
                self.redis_client = None
        else:
            logger.info("Redis cache disabled - using memory fallback")
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            return None
        try:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 300) -> bool:
        """Set value in cache with expiration"""
        if not self.redis_client:
            return False
        try:
            return self.redis_client.setex(key, expire, json.dumps(value, default=str))
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            return False
        try:
            return bool(self.redis_client.delete(key))
        except Exception as e:
            logger.warning(f"Cache delete error: {e}")
            return False


# Global cache instance
cache = CacheService()


class PerformanceService:
    """High-performance database operations service"""
    
    @staticmethod
    def get_user_dashboard_stats(db: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get comprehensive dashboard statistics for a user"""
        cache_key = f"dashboard_stats:{user_id}:{days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Calculate date range
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Single query for all metrics using CTEs (Common Table Expressions)
        if "postgresql" in str(db.bind.url):
            # PostgreSQL optimized query
            query = text("""
                WITH email_stats AS (
                    SELECT 
                        COUNT(*) as total_emails,
                        SUM(CASE WHEN delivered = true THEN 1 ELSE 0 END) as delivered,
                        SUM(CASE WHEN open_count > 0 THEN 1 ELSE 0 END) as opened,
                        SUM(CASE WHEN click_count > 0 THEN 1 ELSE 0 END) as clicked,
                        SUM(CASE WHEN bounced = true THEN 1 ELSE 0 END) as bounced
                    FROM email_trackers 
                    WHERE user_id = :user_id AND created_at >= :start_date
                ),
                campaign_stats AS (
                    SELECT 
                        COUNT(*) as total_campaigns,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_campaigns,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_campaigns
                    FROM campaigns 
                    WHERE user_id = :user_id AND created_at >= :start_date
                ),
                recent_activity AS (
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as emails_sent
                    FROM email_trackers 
                    WHERE user_id = :user_id AND created_at >= :start_date
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                    LIMIT 7
                )
                SELECT 
                    e.*,
                    c.*,
                    array_agg(json_build_object('date', r.date, 'emails_sent', r.emails_sent) ORDER BY r.date DESC) as recent_activity
                FROM email_stats e
                CROSS JOIN campaign_stats c
                LEFT JOIN recent_activity r ON true
                GROUP BY e.total_emails, e.delivered, e.opened, e.clicked, e.bounced, 
                         c.total_campaigns, c.active_campaigns, c.completed_campaigns
            """)
        else:
            # SQLite optimized query
            query = text("""
                SELECT 
                    COUNT(DISTINCT et.id) as total_emails,
                    SUM(CASE WHEN et.delivered = 1 THEN 1 ELSE 0 END) as delivered,
                    SUM(CASE WHEN et.open_count > 0 THEN 1 ELSE 0 END) as opened,
                    SUM(CASE WHEN et.click_count > 0 THEN 1 ELSE 0 END) as clicked,
                    SUM(CASE WHEN et.bounced = 1 THEN 1 ELSE 0 END) as bounced,
                    COUNT(DISTINCT c.id) as total_campaigns,
                    SUM(CASE WHEN c.status = 'active' THEN 1 ELSE 0 END) as active_campaigns,
                    SUM(CASE WHEN c.status = 'completed' THEN 1 ELSE 0 END) as completed_campaigns
                FROM campaigns c
                LEFT JOIN email_trackers et ON et.campaign_id = c.id
                WHERE c.user_id = :user_id 
                AND (et.created_at >= :start_date OR et.created_at IS NULL)
                AND c.created_at >= :start_date
            """)
        
        result = db.execute(query, {"user_id": user_id, "start_date": start_date}).fetchone()
        
        # Get recent activity separately for SQLite
        if "sqlite" in str(db.bind.url):
            activity_query = text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as emails_sent
                FROM email_trackers 
                WHERE user_id = :user_id AND created_at >= :start_date
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 7
            """)
            activity_results = db.execute(activity_query, {"user_id": user_id, "start_date": start_date}).fetchall()
            recent_activity = [{"date": row.date, "emails_sent": row.emails_sent} for row in activity_results]
        else:
            recent_activity = result.recent_activity if result.recent_activity else []
        
        # Calculate rates
        total_emails = result.total_emails or 0
        delivered = result.delivered or 0
        opened = result.opened or 0
        clicked = result.clicked or 0
        
        stats = {
            "total_emails": total_emails,
            "delivered": delivered,
            "opened": opened,
            "clicked": clicked,
            "bounced": result.bounced or 0,
            "delivery_rate": round((delivered / total_emails * 100) if total_emails > 0 else 0, 2),
            "open_rate": round((opened / delivered * 100) if delivered > 0 else 0, 2),
            "click_rate": round((clicked / delivered * 100) if delivered > 0 else 0, 2),
            "total_campaigns": result.total_campaigns or 0,
            "active_campaigns": result.active_campaigns or 0,
            "completed_campaigns": result.completed_campaigns or 0,
            "recent_activity": recent_activity
        }
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, expire=300)
        return stats
    
    @staticmethod
    def get_campaign_performance_batch(db: Session, user_id: int, campaign_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        """Get performance metrics for multiple campaigns in a single query"""
        if not campaign_ids:
            return {}
        
        # Create cache keys for checking
        cache_keys = [f"campaign_perf:{campaign_id}" for campaign_id in campaign_ids]
        cached_results = {}
        uncached_ids = []
        
        # Check cache for each campaign
        for i, campaign_id in enumerate(campaign_ids):
            cached = cache.get(cache_keys[i])
            if cached:
                cached_results[campaign_id] = cached
            else:
                uncached_ids.append(campaign_id)
        
        # Query only uncached campaigns
        if uncached_ids:
            query = text("""
                SELECT 
                    c.id as campaign_id,
                    c.name,
                    c.status,
                    c.created_at,
                    COUNT(et.id) as total_emails,
                    SUM(CASE WHEN et.delivered = 1 THEN 1 ELSE 0 END) as delivered,
                    SUM(CASE WHEN et.open_count > 0 THEN 1 ELSE 0 END) as opened,
                    SUM(CASE WHEN et.click_count > 0 THEN 1 ELSE 0 END) as clicked,
                    SUM(CASE WHEN et.bounced = 1 THEN 1 ELSE 0 END) as bounced,
                    AVG(et.open_count) as avg_opens,
                    AVG(et.click_count) as avg_clicks
                FROM campaigns c
                LEFT JOIN email_trackers et ON et.campaign_id = c.id
                WHERE c.id IN :campaign_ids AND c.user_id = :user_id
                GROUP BY c.id, c.name, c.status, c.created_at
                ORDER BY c.created_at DESC
            """)
            
            results = db.execute(
                query, 
                {"campaign_ids": tuple(uncached_ids), "user_id": user_id}
            ).fetchall()
            
            # Process results and cache them
            for row in results:
                delivered = row.delivered or 0
                total_emails = row.total_emails or 0
                
                performance = {
                    "campaign_id": row.campaign_id,
                    "name": row.name,
                    "status": row.status,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "total_emails": total_emails,
                    "delivered": delivered,
                    "opened": row.opened or 0,
                    "clicked": row.clicked or 0,
                    "bounced": row.bounced or 0,
                    "delivery_rate": round((delivered / total_emails * 100) if total_emails > 0 else 0, 2),
                    "open_rate": round(((row.opened or 0) / delivered * 100) if delivered > 0 else 0, 2),
                    "click_rate": round(((row.clicked or 0) / delivered * 100) if delivered > 0 else 0, 2),
                    "avg_opens": round(row.avg_opens or 0, 2),
                    "avg_clicks": round(row.avg_clicks or 0, 2)
                }
                
                cached_results[row.campaign_id] = performance
                cache.set(f"campaign_perf:{row.campaign_id}", performance, expire=600)
        
        return cached_results
    
    @staticmethod
    def get_deliverability_trends(db: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Get deliverability trends over time"""
        cache_key = f"deliverability_trends:{user_id}:{days}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return cached_result
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = text("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as total_sent,
                SUM(CASE WHEN delivered = 1 THEN 1 ELSE 0 END) as delivered,
                SUM(CASE WHEN bounced = 1 THEN 1 ELSE 0 END) as bounced,
                SUM(CASE WHEN open_count > 0 THEN 1 ELSE 0 END) as opened,
                SUM(CASE WHEN click_count > 0 THEN 1 ELSE 0 END) as clicked
            FROM email_trackers
            WHERE user_id = :user_id 
            AND created_at >= :start_date
            GROUP BY DATE(created_at)
            ORDER BY date ASC
        """)
        
        results = db.execute(query, {"user_id": user_id, "start_date": start_date}).fetchall()
        
        trends = []
        for row in results:
            delivered = row.delivered or 0
            total_sent = row.total_sent or 0
            
            trends.append({
                "date": row.date,
                "total_sent": total_sent,
                "delivered": delivered,
                "bounced": row.bounced or 0,
                "opened": row.opened or 0,
                "clicked": row.clicked or 0,
                "delivery_rate": round((delivered / total_sent * 100) if total_sent > 0 else 0, 2),
                "open_rate": round(((row.opened or 0) / delivered * 100) if delivered > 0 else 0, 2),
                "click_rate": round(((row.clicked or 0) / delivered * 100) if delivered > 0 else 0, 2)
            })
        
        result = {
            "trends": trends,
            "summary": {
                "total_days": len(trends),
                "avg_delivery_rate": round(sum(t["delivery_rate"] for t in trends) / len(trends) if trends else 0, 2),
                "avg_open_rate": round(sum(t["open_rate"] for t in trends) / len(trends) if trends else 0, 2),
                "avg_click_rate": round(sum(t["click_rate"] for t in trends) / len(trends) if trends else 0, 2)
            }
        }
        
        # Cache for 10 minutes
        cache.set(cache_key, result, expire=600)
        return result
    
    @staticmethod
    def invalidate_user_cache(user_id: int):
        """Invalidate all cache entries for a user"""
        patterns = [
            f"dashboard_stats:{user_id}:*",
            f"deliverability_trends:{user_id}:*",
            f"campaign_perf:*"  # Campaign cache doesn't include user_id, so invalidate all
        ]
        
        for pattern in patterns:
            try:
                if cache.redis_client:
                    keys = cache.redis_client.keys(pattern)
                    if keys:
                        cache.redis_client.delete(*keys)
            except Exception as e:
                logger.warning(f"Cache invalidation error for pattern {pattern}: {e}")
