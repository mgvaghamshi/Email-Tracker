"""
API Key management endpoints for programmatic access
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from datetime import datetime, timedelta
import uuid

from ...db import SessionLocal
from ...database.api_key_models import ApiKey, ApiKeyUsage
from ...database.user_models import User
from ...schemas.api_keys import (
    ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse,
    ApiKeyUpdateRequest, ApiKeyUsageStats, ApiKeyListResponse
)
from ...schemas.users import MessageResponse
from ...auth.jwt_auth import get_current_user
from ...core.security import generate_api_key, hash_api_key

router = APIRouter(prefix="/api/v1/auth/api-keys", tags=["Authentication"])


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_new_api_key(
    request: ApiKeyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key for the authenticated user (Dashboard JWT Authentication)
    
    **Note:** The API key will only be shown once in the response. 
    Make sure to save it securely as it cannot be retrieved again.
    
    - **name**: Friendly name for the API key (for your reference)
    - **requests_per_minute**: Rate limit for requests per minute (1-10,000)
    - **requests_per_day**: Rate limit for requests per day (1-1,000,000)
    - **expires_in_days**: Optional expiration in days (1-3,650 days / ~10 years)
    """
    # Generate API key
    api_key = generate_api_key()
    key_hash = hash_api_key(api_key)
    key_prefix = api_key[:11]  # "et_" + first 8 chars
    
    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
    
    # Create API key record
    db_api_key = ApiKey(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        name=request.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        requests_per_minute=request.requests_per_minute,
        requests_per_day=request.requests_per_day,
        is_active=True,
        expires_at=expires_at
    )
    
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    
    # Return response with actual key (only time it's shown)
    return ApiKeyCreateResponse(
        id=db_api_key.id,
        name=db_api_key.name,
        key_prefix=db_api_key.key_prefix,
        requests_per_minute=db_api_key.requests_per_minute,
        requests_per_day=db_api_key.requests_per_day,
        is_active=db_api_key.is_active,
        expires_at=db_api_key.expires_at,
        created_at=db_api_key.created_at,
        last_used_at=db_api_key.last_used_at,
        api_key=api_key  # Only shown once!
    )


@router.get("", response_model=ApiKeyListResponse)
async def list_api_keys(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all API keys for the authenticated user
    
    Returns a list of all API keys owned by the current user 
    (without the actual key values for security).
    Use this to manage your existing API keys.
    """
    api_keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id
    ).all()
    
    return ApiKeyListResponse(
        api_keys=api_keys,
        total=len(api_keys)
    )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key_details(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific API key owned by the authenticated user
    
    Returns information about a specific API key by its ID.
    The actual key value is never returned for security reasons.
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    return api_key


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    request: ApiKeyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an API key's properties owned by the authenticated user
    
    Allows updating the name, active status, and rate limits of an existing API key.
    Cannot update the actual key value for security reasons.
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Update fields if provided
    if request.name is not None:
        api_key.name = request.name
    if request.requests_per_minute is not None:
        api_key.requests_per_minute = request.requests_per_minute
    if request.requests_per_day is not None:
        api_key.requests_per_day = request.requests_per_day
    if request.is_active is not None:
        api_key.is_active = request.is_active
    
    db.commit()
    db.refresh(api_key)
    
    return api_key


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_api_key_endpoint(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete an API key owned by the authenticated user
    
    This will permanently delete the API key and all its usage records.
    This action cannot be undone.
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Delete usage records
    db.query(ApiKeyUsage).filter(ApiKeyUsage.api_key_id == key_id).delete()
    
    # Delete API key
    db.delete(api_key)
    db.commit()
    
    return MessageResponse(message="API key revoked successfully")


@router.get("/{key_id}/usage", response_model=ApiKeyUsageStats)
async def get_api_key_usage(
    key_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get usage statistics for an API key
    
    Returns current usage statistics including requests made in the current
    minute and day, along with rate limits and remaining allowances.
    """
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    
    now = datetime.utcnow()
    current_minute = now.replace(second=0, microsecond=0)
    current_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Get minute usage
    minute_usage = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.window_type == 'minute',
        ApiKeyUsage.window_start == current_minute
    ).first()
    
    # Get day usage
    day_usage = db.query(ApiKeyUsage).filter(
        ApiKeyUsage.api_key_id == key_id,
        ApiKeyUsage.window_type == 'day',
        ApiKeyUsage.window_start == current_day
    ).first()
    
    current_minute_requests = minute_usage.request_count if minute_usage else 0
    current_day_requests = day_usage.request_count if day_usage else 0
    
    return ApiKeyUsageStats(
        api_key_id=api_key.id,
        api_key_name=api_key.name,
        current_minute_requests=current_minute_requests,
        current_day_requests=current_day_requests,
        requests_per_minute_limit=api_key.requests_per_minute,
        requests_per_day_limit=api_key.requests_per_day,
        remaining_minute_requests=max(0, api_key.requests_per_minute - current_minute_requests),
        remaining_day_requests=max(0, api_key.requests_per_day - current_day_requests)
    )


@router.get("/usage/summary", response_model=dict)
async def get_aggregate_api_usage(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get aggregated API usage stats across all API keys
    
    Returns overall usage statistics including:
    - Total requests this month
    - Total available requests 
    - Usage percentage
    - Most used endpoints
    """
    # Get all user's API keys
    api_keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()
    
    if not api_keys:
        return {
            "total_requests_this_month": 0,
            "total_api_keys": 0,
            "active_api_keys": 0,
            "total_daily_limit": 0
        }
    
    # Calculate totals
    total_api_keys = len(api_keys)
    active_api_keys = sum(1 for key in api_keys if key.is_active)
    total_daily_limit = sum(key.requests_per_day for key in api_keys if key.is_active)
    
    # Get this month's usage
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    total_requests_this_month = db.query(func.sum(ApiKeyUsage.request_count)).filter(
        ApiKeyUsage.api_key_id.in_([key.id for key in api_keys]),
        ApiKeyUsage.window_start >= month_start
    ).scalar() or 0
    
    return {
        "total_requests_this_month": total_requests_this_month,
        "total_api_keys": total_api_keys,
        "active_api_keys": active_api_keys,
        "total_daily_limit": total_daily_limit
    }
