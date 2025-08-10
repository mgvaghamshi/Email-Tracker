"""
Authentication and API key management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...core.security import create_api_key, revoke_api_key, get_api_key_info
from ...database.user_models import ApiKey, ApiKeyUsage, User
from ...schemas.auth import (
    ApiKeyCreateRequest, ApiKeyResponse, ApiKeyListResponse,
    ApiKeyUpdateRequest, ApiKeyUsageStats
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_key(
    request: ApiKeyCreateRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """
    Create a new API key for the authenticated user (Dashboard JWT Authentication)
    
    **Note:** The API key will only be shown once in the response. 
    Make sure to save it securely as it cannot be retrieved again.
    
    - **name**: Friendly name for the API key (for your reference)
    - **requests_per_minute**: Rate limit for requests per minute (1-10,000)
    - **requests_per_day**: Rate limit for requests per day (1-1,000,000)
    - **expires_in_days**: Optional expiration in days (1-3,650 days / ~10 years)
    """
    try:
        api_key_string, api_key_record = create_api_key(
            name=request.name,
            user_id=current_user.id,  # Use authenticated user's ID
            requests_per_minute=request.requests_per_minute,
            requests_per_day=request.requests_per_day,
            expires_in_days=request.expires_in_days
        )
        
        return ApiKeyResponse(
            id=api_key_record.id,
            key=api_key_string,  # Only shown during creation
            name=api_key_record.name,
            user_id=api_key_record.user_id,
            is_active=api_key_record.is_active,
            created_at=api_key_record.created_at,
            last_used_at=api_key_record.last_used_at,
            expires_at=api_key_record.expires_at,
            requests_per_minute=api_key_record.requests_per_minute,
            requests_per_day=api_key_record.requests_per_day
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create API key: {str(e)}"
        )


@router.get("/api-keys", response_model=List[ApiKeyListResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> List[ApiKeyListResponse]:
    """
    List all API keys for the authenticated user
    
    Returns a list of all API keys owned by the current user 
    (without the actual key values for security).
    Use this to manage your existing API keys.
    """
    try:
        api_keys = db.query(ApiKey).filter(
            ApiKey.user_id == current_user.id
        ).order_by(ApiKey.created_at.desc()).all()
        return [
            ApiKeyListResponse(
                id=key.id,
                name=key.name,
                user_id=key.user_id,
                is_active=key.is_active,
                created_at=key.created_at,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
                requests_per_minute=key.requests_per_minute,
                requests_per_day=key.requests_per_day
            )
            for key in api_keys
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.get("/api-keys/{key_id}", response_model=ApiKeyListResponse)
async def get_api_key_details(
    key_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> ApiKeyListResponse:
    """
    Get details of a specific API key owned by the authenticated user
    
    Returns information about a specific API key by its ID.
    The actual key value is never returned for security reasons.
    """
    try:
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        return ApiKeyListResponse(
            id=api_key.id,
            name=api_key.name,
            user_id=api_key.user_id,
            is_active=api_key.is_active,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            requests_per_minute=api_key.requests_per_minute,
            requests_per_day=api_key.requests_per_day
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get API key details: {str(e)}"
        )


@router.put("/api-keys/{key_id}", response_model=ApiKeyListResponse)
async def update_api_key(
    key_id: str,
    api_key_request: ApiKeyUpdateRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> ApiKeyListResponse:
    """
    Update an API key's properties owned by the authenticated user
    
    Allows updating the name, active status, and rate limits of an existing API key.
    Cannot update the actual key value for security reasons.
    """
    try:
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Update only the fields that were provided
        if api_key_request.name is not None:
            api_key.name = api_key_request.name
        if api_key_request.is_active is not None:
            api_key.is_active = api_key_request.is_active
        if api_key_request.requests_per_minute is not None:
            api_key.requests_per_minute = api_key_request.requests_per_minute
        if api_key_request.requests_per_day is not None:
            api_key.requests_per_day = api_key_request.requests_per_day
        
        api_key.updated_at = datetime.now()
        db.commit()
        db.refresh(api_key)
        
        return ApiKeyListResponse(
            id=api_key.id,
            name=api_key.name,
            user_id=api_key.user_id,
            is_active=api_key.is_active,
            created_at=api_key.created_at,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            requests_per_minute=api_key.requests_per_minute,
            requests_per_day=api_key.requests_per_day
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API key: {str(e)}"
        )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key_endpoint(
    key_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Delete an API key owned by the authenticated user
    
    This will permanently delete the API key and all its usage records.
    This action cannot be undone.
    """
    try:
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Delete associated usage records first (due to foreign key constraint)
        db.query(ApiKeyUsage).filter(ApiKeyUsage.api_key_id == key_id).delete()
        
        # Delete the API key itself
        db.delete(api_key)
        db.commit()
        
        return None  # 204 No Content
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete API key: {str(e)}"
        )


@router.get("/api-keys/{key_id}/usage", response_model=ApiKeyUsageStats)
async def get_api_key_usage(
    key_id: str, 
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> ApiKeyUsageStats:
    """
    Get usage statistics for an API key
    
    Returns current usage statistics including requests made in the current
    minute and day, along with rate limits and remaining allowances.
    """
    try:
        # Ensure the API key belongs to the authenticated user
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Get current time and calculate time windows
        now = datetime.utcnow()
        minute_ago = now - timedelta(minutes=1)
        day_ago = now - timedelta(days=1)
        
        # Query actual usage from database
        current_minute_requests = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.timestamp >= minute_ago
        ).count()
        
        current_day_requests = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.timestamp >= day_ago
        ).count()
        
        # Calculate remaining allowances
        remaining_minute = max(0, api_key.requests_per_minute - current_minute_requests)
        remaining_day = max(0, api_key.requests_per_day - current_day_requests)
        
        return ApiKeyUsageStats(
            api_key_id=api_key.id,
            current_minute_requests=current_minute_requests,
            current_day_requests=current_day_requests,
            limit_minute=api_key.requests_per_minute,
            limit_day=api_key.requests_per_day,
            remaining_minute=remaining_minute,
            remaining_day=remaining_day
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get API key usage: {str(e)}"
        )


@router.get("/api-keys/usage/summary")
async def get_aggregate_api_usage(db: Session = Depends(get_db)):
    """
    Get aggregated API usage stats across all API keys
    
    Returns overall usage statistics including:
    - Total requests this month
    - Total available requests 
    - Usage percentage
    - Most used endpoints
    """
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        # Get current month boundaries
        now = datetime.utcnow()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get all active API keys
        api_keys = db.query(ApiKey).filter(ApiKey.is_active == True).all()
        
        if not api_keys:
            return {
                "total_requests_this_month": 0,
                "total_monthly_limit": 0,
                "usage_percentage": 0,
                "api_keys_count": 0,
                "most_used_endpoints": []
            }
        
        # Calculate totals
        total_monthly_limit = sum(key.requests_per_day * 30 for key in api_keys)  # Approximate monthly limit
        api_key_ids = [key.id for key in api_keys]
        
        # Count requests this month
        total_requests_this_month = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id.in_(api_key_ids),
            ApiKeyUsage.timestamp >= month_start
        ).count()
        
        # Calculate usage percentage
        usage_percentage = int((total_requests_this_month / total_monthly_limit * 100) if total_monthly_limit > 0 else 0)
        
        # Get most used endpoints this month
        endpoint_stats = db.query(
            ApiKeyUsage.endpoint,
            func.count(ApiKeyUsage.id).label('count')
        ).filter(
            ApiKeyUsage.api_key_id.in_(api_key_ids),
            ApiKeyUsage.timestamp >= month_start
        ).group_by(ApiKeyUsage.endpoint).order_by(func.count(ApiKeyUsage.id).desc()).limit(5).all()
        
        most_used_endpoints = [
            {
                "endpoint": endpoint,
                "requests": count
            }
            for endpoint, count in endpoint_stats
        ]
        
        return {
            "total_requests_this_month": total_requests_this_month,
            "total_monthly_limit": total_monthly_limit,
            "usage_percentage": min(usage_percentage, 100),  # Cap at 100%
            "api_keys_count": len(api_keys),
            "most_used_endpoints": most_used_endpoints
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get aggregate usage stats: {str(e)}"
        )
