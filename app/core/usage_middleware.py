"""
API Usage tracking middleware and dependency
Production-ready, clean implementation
"""
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import time
import bcrypt
import calendar

from ..database.user_models import ApiKey, ApiKeyUsage
from ..dependencies import get_db
from .logging_config import get_logger
from datetime import datetime, timedelta

logger = get_logger("core.usage_middleware")


async def get_api_key_from_request(request: Request, db: Session = Depends(get_db)) -> Optional[ApiKey]:
    """
    Extract and validate API key from request headers
    Uses prefix-based lookup for efficiency, then bcrypt validation
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    
    if not authorization.startswith("Bearer "):
        return None
    
    api_key_string = authorization[7:]  # Remove "Bearer " prefix
    
    if not api_key_string or len(api_key_string) < 8:
        return None
    
    # Extract prefix from API key (first 8 characters)
    prefix = api_key_string[:8]
    
    # Find API key by prefix first (efficient database lookup)
    api_key = db.query(ApiKey).filter(
        ApiKey.prefix == prefix,
        ApiKey.is_active == True,
        ApiKey.revoked == False
    ).first()
    
    if not api_key:
        return None
    
    # Verify the full API key with bcrypt
    try:
        if bcrypt.checkpw(api_key_string.encode('utf-8'), api_key.hashed_key.encode('utf-8')):
            # Check if the API key is still valid (not expired)
            if api_key.is_valid():
                return api_key
    except (ValueError, AttributeError):
        # Invalid hash format or other bcrypt error
        pass
    
    return None


async def track_api_usage_middleware(request: Request, db: Session = Depends(get_db)):
    """
    Middleware to track API usage and enforce rate limits for API key requests
    Only called for API endpoints that may require API keys
    """
    # Get API key from request
    api_key = await get_api_key_from_request(request, db)
    
    if not api_key:
        # No API key provided or invalid - don't track or enforce limits
        # This is normal for public API endpoints
        return
    
    # Check rate limits before processing request
    now = datetime.utcnow()
    minute_ago = now - timedelta(minutes=1)
    day_ago = now - timedelta(days=1)
    
    # Count recent requests
    minute_requests = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == api_key.id,
        ApiKeyUsage.timestamp >= minute_ago
    ).count()
    
    day_requests = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == api_key.id,
        ApiKeyUsage.timestamp >= day_ago  
    ).count()
    
    # Enforce rate limits
    if minute_requests >= api_key.requests_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many requests per minute",
                "limit": api_key.requests_per_minute,
                "window": "1 minute"
            }
        )
    
    if day_requests >= api_key.requests_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded", 
                "message": "Too many requests per day",
                "limit": api_key.requests_per_day,
                "window": "1 day"
            }
        )
    
    # Record API usage
    start_time = time.time()
    
    try:
        # Record usage in database
        usage_record = ApiKeyUsage(
            api_key_id=api_key.id,
            endpoint=request.url.path,
            method=request.method,
            status_code=200,  # Default success status
            response_time_ms=int((time.time() - start_time) * 1000),
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            timestamp=now
        )
        
        db.add(usage_record)
        
        # Update API key usage statistics
        api_key.update_usage()
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        # Log the error but don't break the request
        logger.error(f"Error recording API usage: {e}")


# Dependency for endpoints that require API key authentication
async def require_api_key(request: Request, db: Session = Depends(get_db)) -> ApiKey:
    """
    Dependency that requires a valid API key
    Use this for endpoints that need API key authentication
    """
    api_key = await get_api_key_from_request(request, db)
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Authentication required",
                "message": "Valid API key required"
            }
        )
    
    return api_key


# Dependency for endpoints that require specific scopes
def require_scopes(*required_scopes: str):
    """
    Dependency factory that requires specific API key scopes
    Usage: @app.get("/endpoint", dependencies=[Depends(require_scopes("emails:send"))])
    """
    async def scope_dependency(api_key: ApiKey = Depends(require_api_key)) -> ApiKey:
        if not api_key.has_any_scope(list(required_scopes)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "Insufficient permissions",
                    "message": f"Required scopes: {', '.join(required_scopes)}",
                    "your_scopes": api_key.scope_list
                }
            )
        return api_key
    
    return scope_dependency
    minute_reset = calendar.timegm((now + timedelta(minutes=1)).timetuple())
    day_reset = calendar.timegm((now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).timetuple())
    
    if minute_requests >= api_key.requests_per_minute:
        # Store rate limit info for response headers first
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit-Minute": str(api_key.requests_per_minute),
            "X-RateLimit-Remaining-Minute": "0",
            "X-RateLimit-Reset-Minute": str(minute_reset),
            "X-RateLimit-Limit-Day": str(api_key.requests_per_day),
            "X-RateLimit-Remaining-Day": str(remaining_day),
            "X-RateLimit-Reset-Day": str(day_reset),
            "X-RateLimit-Usage-Minute": str(minute_requests),
            "X-RateLimit-Usage-Day": str(day_requests),
            "X-RateLimit-Type": "per_minute",
            "Retry-After": "60"
        }
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": "You've hit your per-minute limit. Wait or upgrade your plan.",
                "retry_after_seconds": 60,
                "limit_type": "per_minute",
                "limit": api_key.requests_per_minute,
                "current_usage": minute_requests,
                "reset_time": minute_reset
            },
            headers={
                "X-RateLimit-Limit": str(api_key.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(minute_reset),
                "Retry-After": "60",
                "X-RateLimit-Type": "per_minute"
            }
        )
    
    if day_requests >= api_key.requests_per_day:
        # Store rate limit info for response headers first
        request.state.rate_limit_headers = {
            "X-RateLimit-Limit-Minute": str(api_key.requests_per_minute),
            "X-RateLimit-Remaining-Minute": str(remaining_minute),
            "X-RateLimit-Reset-Minute": str(minute_reset),
            "X-RateLimit-Limit-Day": str(api_key.requests_per_day),
            "X-RateLimit-Remaining-Day": "0",
            "X-RateLimit-Reset-Day": str(day_reset),
            "X-RateLimit-Usage-Minute": str(minute_requests),
            "X-RateLimit-Usage-Day": str(day_requests),
            "X-RateLimit-Type": "per_day",
            "Retry-After": str(int((day_reset - calendar.timegm(now.timetuple()))))
        }
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Daily rate limit exceeded",
                "message": "You've hit your daily limit. Wait until midnight UTC or upgrade your plan.",
                "retry_after_seconds": int((day_reset - calendar.timegm(now.timetuple()))),
                "limit_type": "per_day",
                "limit": api_key.requests_per_day,
                "current_usage": day_requests,
                "reset_time": day_reset
            },
            headers={
                "X-RateLimit-Limit": str(api_key.requests_per_day),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(day_reset),
                "Retry-After": str(int((day_reset - calendar.timegm(now.timetuple())))),
                "X-RateLimit-Type": "per_day"
            }
        )
    
    # Store rate limit info for response headers
    request.state.rate_limit_headers = {
        "X-RateLimit-Limit-Minute": str(api_key.requests_per_minute),
        "X-RateLimit-Remaining-Minute": str(remaining_minute),
        "X-RateLimit-Reset-Minute": str(minute_reset),
        "X-RateLimit-Limit-Day": str(api_key.requests_per_day),
        "X-RateLimit-Remaining-Day": str(remaining_day),
        "X-RateLimit-Reset-Day": str(day_reset),
        "X-RateLimit-Usage-Minute": str(minute_requests),
        "X-RateLimit-Usage-Day": str(day_requests)
    }
    
    # Store request info for later tracking
    request.state.api_key_id = api_key.id
    request.state.start_time = start_time
    request.state.should_track = True


def track_api_response(
    request: Request,
    response_status: int,
    response,
    db: Session
):
    """
    Track the API response after processing and add rate limit headers
    """
    # Add rate limit headers if available
    if hasattr(request.state, 'rate_limit_headers'):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    
    if not hasattr(request.state, 'should_track') or not request.state.should_track:
        return
    
    try:
        # Calculate response time
        response_time_ms = int((time.time() - request.state.start_time) * 1000)
        
        # Get client info
        user_agent = request.headers.get("User-Agent", "")
        client_ip = request.client.host if request.client else ""
        
        # Create usage record
        usage_record = ApiKeyUsage(
            api_key_id=request.state.api_key_id,
            endpoint=request.url.path,
            method=request.method,
            status_code=response_status,
            request_time=datetime.utcnow(),
            response_time_ms=response_time_ms,
            user_agent=user_agent,
            ip_address=client_ip
        )
        
        db.add(usage_record)
        
        # Update last_used_at for the API key
        api_key = db.query(ApiKey).filter(ApiKey.id == request.state.api_key_id).first()
        if api_key:
            api_key.last_used_at = datetime.utcnow()
        
        db.commit()
        
    except Exception as e:
        logger.error(f"Error tracking API usage: {e}")
        db.rollback()
