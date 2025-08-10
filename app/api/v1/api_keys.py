"""
API Key management endpoints for per-user dynamic API key handling
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import logging

from ...enhanced_dependencies import (
    get_db, get_current_verified_user, verify_api_key_scope, require_scope
)
from ...database.user_models import User, ApiKey, ApiKeyUsage, API_KEY_SCOPES, SCOPE_PRESETS
from ...schemas.api_keys import (
    ApiKeyCreate, ApiKeyResponse, ApiKeyListResponse, ApiKeyUpdate,
    ApiKeyUsageResponse, ApiKeyStatsResponse, MessageResponse
)

router = APIRouter(prefix="/api-keys", tags=["API Key Management"])
logger = logging.getLogger(__name__)


@router.post("/", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """
    Create a new API key for the authenticated user
    
    **Features:**
    - Dynamically generated secure API key
    - bcrypt hashed storage
    - Custom scopes and rate limits
    - Optional expiration
    
    **Scopes Available:**
    See /api-keys/scopes endpoint for full list
    
    **Rate Limiting:**
    - Default: 100 requests/minute, 10,000 requests/day
    - Can be customized per key
    """
    try:
        # Validate scopes
        invalid_scopes = [scope for scope in key_data.scopes if scope not in API_KEY_SCOPES]
        if invalid_scopes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
            )
        
        # Check if user already has a key with this name
        existing_key = db.query(ApiKey).filter(
            ApiKey.user_id == current_user.id,
            ApiKey.name == key_data.name,
            ApiKey.revoked == False
        ).first()
        
        if existing_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"API key with name '{key_data.name}' already exists"
            )
        
        # Generate new API key
        raw_key, prefix = ApiKey.generate_key()
        hashed_key = ApiKey.hash_key(raw_key)
        
        # Set expiration if specified
        expires_at = None
        if key_data.expires_in_days:
            expires_at = datetime.utcnow() + timedelta(days=key_data.expires_in_days)
        
        # Create API key record
        api_key = ApiKey(
            user_id=current_user.id,
            name=key_data.name,
            hashed_key=hashed_key,
            prefix=prefix,
            scopes=key_data.scopes or ['*'],  # Default to full access if no scopes specified
            requests_per_minute=key_data.requests_per_minute or 100,
            requests_per_day=key_data.requests_per_day or 10000,
            expires_at=expires_at
        )
        
        db.add(api_key)
        db.commit()
        db.refresh(api_key)
        
        logger.info(f"Created API key '{key_data.name}' for user {current_user.id}")
        
        return ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=raw_key,  # Only returned once during creation
            prefix=api_key.prefix,
            scopes=api_key.scopes,
            requests_per_minute=api_key.requests_per_minute,
            requests_per_day=api_key.requests_per_day,
            is_active=api_key.is_active,
            usage_count=api_key.usage_count,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create API key: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.get("/", response_model=ApiKeyListResponse)
async def list_api_keys(
    skip: int = 0,
    limit: int = 50,
    include_revoked: bool = False,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> ApiKeyListResponse:
    """
    List all API keys for the authenticated user
    
    **Query Parameters:**
    - **skip**: Number of keys to skip (pagination)
    - **limit**: Maximum number of keys to return
    - **include_revoked**: Include revoked keys in results
    """
    try:
        # Build query
        query = db.query(ApiKey).filter(ApiKey.user_id == current_user.id)
        
        if not include_revoked:
            query = query.filter(ApiKey.revoked == False)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        api_keys = query.order_by(ApiKey.created_at.desc()).offset(skip).limit(limit).all()
        
        # Convert to response format (without raw keys)
        keys_data = []
        for key in api_keys:
            keys_data.append(ApiKeyResponse(
                id=key.id,
                name=key.name,
                key=None,  # Never return raw key in list
                prefix=key.prefix,
                scopes=key.scopes,
                requests_per_minute=key.requests_per_minute,
                requests_per_day=key.requests_per_day,
                is_active=key.is_active,
                revoked=key.revoked,
                revoked_at=key.revoked_at,
                usage_count=key.usage_count,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
                created_at=key.created_at,
                updated_at=key.updated_at
            ))
        
        return ApiKeyListResponse(
            keys=keys_data,
            total=total,
            skip=skip,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to list API keys: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API keys"
        )


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """Get details of a specific API key"""
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
        
        return ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=None,  # Never return raw key
            prefix=api_key.prefix,
            scopes=api_key.scopes,
            requests_per_minute=api_key.requests_per_minute,
            requests_per_day=api_key.requests_per_day,
            is_active=api_key.is_active,
            revoked=api_key.revoked,
            revoked_at=api_key.revoked_at,
            revoked_reason=api_key.revoked_reason,
            usage_count=api_key.usage_count,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve API key"
        )


@router.put("/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: str,
    key_update: ApiKeyUpdate,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """
    Update an API key's settings
    
    **Note:** The actual key value cannot be changed. 
    Create a new key and revoke the old one if needed.
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
        
        if api_key.revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update revoked API key"
            )
        
        # Validate scopes if provided
        if key_update.scopes is not None:
            invalid_scopes = [scope for scope in key_update.scopes if scope not in API_KEY_SCOPES]
            if invalid_scopes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid scopes: {', '.join(invalid_scopes)}"
                )
            api_key.scopes = key_update.scopes
        
        # Update fields
        if key_update.name is not None:
            # Check for name conflicts
            existing = db.query(ApiKey).filter(
                ApiKey.user_id == current_user.id,
                ApiKey.name == key_update.name,
                ApiKey.id != key_id,
                ApiKey.revoked == False
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"API key with name '{key_update.name}' already exists"
                )
            
            api_key.name = key_update.name
        
        if key_update.is_active is not None:
            api_key.is_active = key_update.is_active
        
        if key_update.requests_per_minute is not None:
            api_key.requests_per_minute = key_update.requests_per_minute
        
        if key_update.requests_per_day is not None:
            api_key.requests_per_day = key_update.requests_per_day
        
        if key_update.expires_in_days is not None:
            if key_update.expires_in_days > 0:
                api_key.expires_at = datetime.utcnow() + timedelta(days=key_update.expires_in_days)
            else:
                api_key.expires_at = None
        
        api_key.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(api_key)
        
        logger.info(f"Updated API key {key_id} for user {current_user.id}")
        
        return ApiKeyResponse(
            id=api_key.id,
            name=api_key.name,
            key=None,
            prefix=api_key.prefix,
            scopes=api_key.scopes,
            requests_per_minute=api_key.requests_per_minute,
            requests_per_day=api_key.requests_per_day,
            is_active=api_key.is_active,
            revoked=api_key.revoked,
            usage_count=api_key.usage_count,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
            updated_at=api_key.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update API key"
        )


@router.delete("/{key_id}", response_model=MessageResponse)
async def revoke_api_key(
    key_id: str,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Revoke an API key (mark as inactive and revoked)
    
    **Note:** This action cannot be undone. The key will immediately 
    stop working for all future requests.
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
        
        if api_key.revoked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API key is already revoked"
            )
        
        # Revoke the key
        api_key.revoked = True
        api_key.is_active = False
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_reason = reason or "Manually revoked by user"
        api_key.updated_at = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Revoked API key {key_id} for user {current_user.id}")
        
        return MessageResponse(
            message=f"API key '{api_key.name}' has been revoked successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to revoke API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke API key"
        )


@router.get("/{key_id}/usage", response_model=List[ApiKeyUsageResponse])
async def get_api_key_usage(
    key_id: str,
    days: int = 7,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> List[ApiKeyUsageResponse]:
    """
    Get usage logs for a specific API key
    
    **Query Parameters:**
    - **days**: Number of days of history to retrieve (default: 7)
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    try:
        # Verify key ownership
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Get usage logs
        since_date = datetime.utcnow() - timedelta(days=days)
        
        usage_logs = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.request_time >= since_date
        ).order_by(
            ApiKeyUsage.request_time.desc()
        ).offset(skip).limit(limit).all()
        
        return [
            ApiKeyUsageResponse(
                id=log.id,
                endpoint=log.endpoint,
                method=log.method,
                status_code=log.status_code,
                request_time=log.request_time,
                response_time_ms=log.response_time_ms,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                error_message=log.error_message
            )
            for log in usage_logs
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get usage for API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage logs"
        )


@router.get("/{key_id}/stats", response_model=ApiKeyStatsResponse)
async def get_api_key_stats(
    key_id: str,
    days: int = 30,
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> ApiKeyStatsResponse:
    """
    Get usage statistics for a specific API key
    
    **Query Parameters:**
    - **days**: Number of days to analyze (default: 30)
    """
    try:
        # Verify key ownership
        api_key = db.query(ApiKey).filter(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id
        ).first()
        
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Calculate stats
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Total requests
        total_requests = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.request_time >= since_date
        ).count()
        
        # Success rate
        successful_requests = db.query(ApiKeyUsage).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.request_time >= since_date,
            ApiKeyUsage.status_code < 400
        ).count()
        
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        # Most used endpoints
        from sqlalchemy import func
        top_endpoints = db.query(
            ApiKeyUsage.endpoint,
            func.count(ApiKeyUsage.id).label('count')
        ).filter(
            ApiKeyUsage.api_key_id == key_id,
            ApiKeyUsage.request_time >= since_date
        ).group_by(
            ApiKeyUsage.endpoint
        ).order_by(
            func.count(ApiKeyUsage.id).desc()
        ).limit(5).all()
        
        return ApiKeyStatsResponse(
            total_requests=total_requests,
            successful_requests=successful_requests,
            success_rate=round(success_rate, 2),
            period_days=days,
            top_endpoints=[
                {"endpoint": endpoint, "count": count}
                for endpoint, count in top_endpoints
            ],
            last_used_at=api_key.last_used_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stats for API key {key_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve key statistics"
        )


@router.get("/scopes/available")
async def get_available_scopes(
    current_user: User = Depends(get_current_verified_user)
) -> dict:
    """
    Get list of all available API key scopes and presets
    
    **Returns:**
    - **scopes**: Dictionary of all available scopes and their descriptions
    - **presets**: Pre-configured scope combinations for common use cases
    """
    return {
        "scopes": API_KEY_SCOPES,
        "presets": SCOPE_PRESETS
    }
