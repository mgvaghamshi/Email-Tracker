"""
Tracking service for email opens, clicks, and bot detection
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from ..database.models import EmailTracker, EmailEvent, EmailClick

logger = logging.getLogger(__name__)


class TrackingService:
    """Service for handling email tracking events"""
    
    def __init__(self):
        # Bot detection keywords (conservative approach)
        self.bot_keywords = [
            'googlebot', 'bingbot', 'slurp', 'duckduckbot', 'baiduspider',
            'yandexbot', 'facebookexternalhit', 'twitterbot', 'linkedinbot',
            'crawler', 'spider', 'scraper', 'headless',
            'phantom', 'selenium', 'webdriver', 'automation',
            'curl/', 'wget/', 'python-requests/', 'postman'
        ]
    
    def detect_bot(self, user_agent: str, ip_address: Optional[str] = None) -> Tuple[bool, Optional[str], float]:
        """
        Detect if a request is from a bot
        
        Returns:
            (is_bot, reason, confidence_score)
        """
        if not user_agent:
            return True, "empty_user_agent", 1.0
        
        user_agent_lower = user_agent.lower()
        
        # Check for obvious bot keywords
        for keyword in self.bot_keywords:
            if keyword in user_agent_lower:
                return True, f"bot_keyword: {keyword}", 0.95
        
        # Check for suspicious patterns
        if len(user_agent) < 10:
            return True, "suspiciously_short_user_agent", 0.8
        
        # More sophisticated checks could be added here:
        # - IP reputation checking
        # - Request frequency analysis
        # - Behavioral patterns
        
        return False, None, 0.95
    
    async def track_open(
        self,
        tracker_id: str,
        user_agent: str,
        ip_address: Optional[str],
        db: Session
    ) -> bool:
        """
        Track an email open event
        
        Returns:
            bool: Whether the event was tracked (not filtered as bot/duplicate)
        """
        try:
            # Get tracker
            tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
            if not tracker:
                return False
            
            # Bot detection
            is_bot, bot_reason, confidence = self.detect_bot(user_agent, ip_address)
            
            # Check for recent duplicate from same IP (within 3 seconds)
            if not is_bot and ip_address:
                recent_threshold = datetime.utcnow() - timedelta(seconds=3)
                recent_event = db.query(EmailEvent).filter(
                    EmailEvent.tracker_id == tracker_id,
                    EmailEvent.event_type == "open",
                    EmailEvent.timestamp > recent_threshold,
                    EmailEvent.ip_address == ip_address
                ).first()
                
                if recent_event:
                    logger.info(f"🔄 DUPLICATE FILTERED: {tracker_id} | Recent open within 3 seconds | IP: {ip_address}")
                    return False
            
            # Decide whether to track
            should_track = not is_bot
            
            if should_track:
                # Track the open
                if not tracker.opened_at:
                    tracker.opened_at = datetime.utcnow()
                    tracker.unique_opens = 1
                
                tracker.open_count += 1
                tracker.updated_at = datetime.utcnow()
                
                # Create event record
                event = EmailEvent(
                    id=str(uuid.uuid4()),
                    tracker_id=tracker_id,
                    event_type="open",
                    timestamp=datetime.utcnow(),
                    user_agent=user_agent,
                    ip_address=ip_address,
                    is_bot=False
                )
                db.add(event)
                db.commit()
                
                logger.info(f"✅ TRACKED: Email open for {tracker_id} | IP: {ip_address} | UA: {user_agent[:100]}")
                return True
            else:
                # Log filtered event
                logger.info(f"🤖 BOT FILTERED: {tracker_id} | Reason: {bot_reason} | UA: {user_agent[:100]}")
                
                # Still create event record for analytics but mark as bot
                event = EmailEvent(
                    id=str(uuid.uuid4()),
                    tracker_id=tracker_id,
                    event_type="open",
                    timestamp=datetime.utcnow(),
                    user_agent=user_agent,
                    ip_address=ip_address,
                    is_bot=True,
                    bot_reason=bot_reason
                )
                db.add(event)
                db.commit()
                
                return False
                
        except Exception as e:
            logger.error(f"❌ ERROR tracking open: {str(e)}")
            return False
    
    async def track_click(
        self,
        tracker_id: str,
        url: str,
        user_agent: str,
        ip_address: Optional[str],
        referrer: Optional[str],
        db: Session
    ) -> bool:
        """
        Track an email click event
        
        Returns:
            bool: Whether the event was tracked (not filtered as duplicate)
        """
        try:
            # Get tracker
            tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
            if not tracker:
                return False
            
            # Check for duplicate clicks (same URL, IP within 5 seconds)
            recent_threshold = datetime.utcnow() - timedelta(seconds=5)
            recent_click = db.query(EmailClick).filter(
                EmailClick.tracker_id == tracker_id,
                EmailClick.url == url,
                EmailClick.timestamp > recent_threshold,
                EmailClick.ip_address == ip_address
            ).first()
            
            if recent_click:
                logger.info(f"🔄 Duplicate click ignored for {tracker_id} -> {url}")
                return False
            
            # Track the click
            if not tracker.first_click_at:
                tracker.first_click_at = datetime.utcnow()
                tracker.unique_clicks = 1
            
            tracker.click_count += 1
            tracker.updated_at = datetime.utcnow()
            
            # Create click record
            click = EmailClick(
                id=str(uuid.uuid4()),
                tracker_id=tracker_id,
                url=url,
                timestamp=datetime.utcnow(),
                user_agent=user_agent,
                ip_address=ip_address,
                referrer=referrer
            )
            db.add(click)
            
            # Create event record
            event = EmailEvent(
                id=str(uuid.uuid4()),
                tracker_id=tracker_id,
                event_type="click",
                timestamp=datetime.utcnow(),
                user_agent=user_agent,
                ip_address=ip_address,
                is_bot=False
            )
            db.add(event)
            db.commit()
            
            logger.info(f"✅ Click tracked for {tracker_id} -> {url}")
            return True
            
        except Exception as e:
            logger.error(f"❌ ERROR tracking click: {str(e)}")
            return False
