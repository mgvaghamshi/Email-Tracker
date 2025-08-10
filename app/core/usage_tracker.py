"""
API Usage tracking utilities
"""
from sqlalchemy.orm import Session
from ..database.user_models import ApiKeyUsage, ApiKey
from .logging_config import get_logger
from datetime import datetime
import time

logger = get_logger("core.usage_tracker")


def track_api_usage(
    db: Session,
    api_key_id: str,
    endpoint: str,
    method: str,
    status_code: int,
    start_time: float,
    user_agent: str = None,
    ip_address: str = None
):
    """
    Track API usage for rate limiting and analytics
    
    Args:
        db: Database session
        api_key_id: The API key ID that made the request
        endpoint: The API endpoint that was called
        method: HTTP method (GET, POST, etc.)
        status_code: HTTP response status code
        start_time: Request start time (from time.time())
        user_agent: User agent string
        ip_address: Client IP address
    """
    try:
        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)
        
        # Create usage record
        usage_record = ApiKeyUsage(
            api_key_id=api_key_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            request_time=datetime.utcnow(),
            response_time_ms=response_time_ms,
            user_agent=user_agent,
            ip_address=ip_address
        )
        
        db.add(usage_record)
        
        # Update last_used_at for the API key
        api_key = db.query(ApiKey).filter(ApiKey.id == api_key_id).first()
        if api_key:
            api_key.last_used_at = datetime.utcnow()
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error tracking API usage: {e}")
        db.rollback()
