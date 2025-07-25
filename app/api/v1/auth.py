"""
Authentication and API key management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from ...dependencies import get_db
from ...core.security import create_api_key, revoke_api_key, get_api_key_info
from ...database.models import ApiKey
from ...schemas.auth import (
    ApiKeyCreateRequest, ApiKeyResponse, ApiKeyListResponse,
    ApiKeyUpdateRequest, ApiKeyUsageStats
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_key(
    request: ApiKeyCreateRequest,
    db: Session = Depends(get_db)
) -> ApiKeyResponse:
    """
    Create a new API key
    
    **Note:** The API key will only be shown once in the response. 
    Make sure to save it securely as it cannot be retrieved again.
    
    - **name**: Friendly name for the API key (for your reference)
    - **user_id**: Optional user ID to associate with this key
    - **requests_per_minute**: Rate limit for requests per minute (1-10,000)
    - **requests_per_day**: Rate limit for requests per day (1-1,000,000)
    - **expires_in_days**: Optional expiration in days (1-3,650 days / ~10 years)
    """
    try:
        api_key_string, api_key_record = create_api_key(
            name=request.name,
            user_id=request.user_id,
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
async def list_api_keys(db: Session = Depends(get_db)) -> List[ApiKeyListResponse]:
    """
    List all API keys
    
    Returns a list of all API keys (without the actual key values for security).
    Use this to manage your existing API keys.
    """
    try:
        api_keys = db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()
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
async def get_api_key_details(key_id: str, db: Session = Depends(get_db)) -> ApiKeyListResponse:
    """
    Get details of a specific API key
    
    Returns information about a specific API key by its ID.
    The actual key value is never returned for security reasons.
    """
    try:
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
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


@router.patch("/api-keys/{key_id}", response_model=ApiKeyListResponse)
async def update_api_key(
    key_id: str,
    request: ApiKeyUpdateRequest,
    db: Session = Depends(get_db)
) -> ApiKeyListResponse:
    """
    Update an API key
    
    Update the settings of an existing API key. You can change:
    - **name**: Friendly name
    - **is_active**: Enable or disable the key
    - **requests_per_minute**: Change rate limit per minute
    - **requests_per_day**: Change rate limit per day
    """
    try:
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        # Update fields if provided
        if request.name is not None:
            api_key.name = request.name
        if request.is_active is not None:
            api_key.is_active = request.is_active
        if request.requests_per_minute is not None:
            api_key.requests_per_minute = request.requests_per_minute
        if request.requests_per_day is not None:
            api_key.requests_per_day = request.requests_per_day
        
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update API key: {str(e)}"
        )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key_endpoint(key_id: str, db: Session = Depends(get_db)):
    """
    Revoke (deactivate) an API key
    
    This will immediately deactivate the API key, preventing it from being used
    for future requests. This action cannot be undone - you'll need to create
    a new API key if needed.
    """
    try:
        api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        
        api_key.is_active = False
        db.commit()
        
        return None  # 204 No Content
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )
