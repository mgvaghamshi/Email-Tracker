"""
API Key-based authentication for external programmatic access

Handles API key validation, permissions checking, and usage tracking for external clients.
"""
from fastapi import Depends, HTTPException, Security, status, Request
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session
from typing import Optional, Tuple
from datetime import datetime
import json

from ..database.connection import get_db
from ..database.user_models import User, ApiKey, ApiKeyUsage
from ..core.security import get_api_key_info
from ..core.logging_config import get_logger
from .middleware import AuthConfig, require_active_user

logger = get_logger("auth.api_key_auth")

# Custom API key header (x-api-key instead of Authorization)
api_key_header = APIKeyHeader(name=AuthConfig.API_KEY_HEADER_NAME, auto_error=False)


async def get_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
    db: Session = Depends(get_db)
) -> User:
    """
    Get authenticated user from API key (for external programmatic access)
    
    Expected header: x-api-key: <API_KEY>
    
    Returns:
        User: The user associated with the API key
        
    Raises:
        HTTPException: 403 if API key is invalid, expired, or deactivated
    """
    if not api_key:
        logger.warning("❌ API Key authentication failed: No API key provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AuthConfig.get_error_messages()["api_key_required"],
        )
    
    logger.debug(f"🔑 API Key token received: {api_key[:10]}...{api_key[-10:] if len(api_key) > 20 else '***'}")
    
    try:
        # Look up API key in database
        api_key_obj = get_api_key_info(api_key)
        if not api_key_obj:
            logger.warning(f"❌ API Key authentication failed: Invalid API key {api_key[:10]}...")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AuthConfig.get_error_messages()["api_key_invalid"],
            )
        
        # Check if API key is active
        if not api_key_obj.is_active:
            logger.warning(f"❌ API Key authentication failed: Inactive API key {api_key_obj.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AuthConfig.get_error_messages()["api_key_inactive"],
            )
        
        # Check if API key is expired
        if api_key_obj.expires_at and api_key_obj.expires_at < datetime.utcnow():
            logger.warning(f"❌ API Key authentication failed: Expired API key {api_key_obj.id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=AuthConfig.get_error_messages()["api_key_expired"],
            )
        
        # Get associated user
        user = db.query(User).filter(User.id == api_key_obj.user_id).first()
        if not user:
            logger.error(f"API key {api_key_obj.id} has no associated user")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key - no associated user",
            )
        
        # Check if user is active
        require_active_user(user)
        
        # Log API key usage
        await _log_api_key_usage(api_key_obj, request, db)
        
        # Update last used timestamp
        api_key_obj.last_used_at = datetime.utcnow()
        api_key_obj.usage_count = (api_key_obj.usage_count or 0) + 1
        db.commit()
        
        logger.info(f"✅ API Key authentication successful for user: {user.email}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ API Key authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=AuthConfig.get_error_messages()["api_key_invalid"],
        )


async def get_user_and_api_key(
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Tuple[User, ApiKey]:
    """
    Get both user and API key object for endpoints that need API key details
    
    Returns:
        Tuple[User, ApiKey]: The user and API key objects
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key required. Include 'x-api-key' header with your API key.",
        )
    
    # Get user (this also validates the API key)
    user = await get_user_from_api_key(api_key, request, db)
    
    # Get API key object
    api_key_obj = get_api_key_info(api_key)
    
    return user, api_key_obj


async def check_api_key_permission(
    api_key_obj: ApiKey,
    required_scope: str
) -> bool:
    """
    Check if API key has the required permission/scope
    
    Args:
        api_key_obj: The API key object
        required_scope: The required scope (e.g., "campaigns:read", "emails:send")
        
    Returns:
        bool: True if permission granted, False otherwise
    """
    if not api_key_obj.scopes:
        return False
    
    try:
        scopes = json.loads(api_key_obj.scopes) if isinstance(api_key_obj.scopes, str) else api_key_obj.scopes
        
        # Check for exact scope match or wildcard
        if required_scope in scopes or "*" in scopes:
            return True
        
        # Check for parent scope (e.g., "campaigns:*" covers "campaigns:read")
        scope_parts = required_scope.split(":")
        if len(scope_parts) == 2:
            parent_scope = f"{scope_parts[0]}:*"
            if parent_scope in scopes:
                return True
        
        return False
        
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Invalid scopes format for API key {api_key_obj.id}")
        return False


async def require_api_key_scope(
    required_scope: str,
    api_key_user: Tuple[User, ApiKey] = Depends(get_user_and_api_key)
) -> User:
    """
    Dependency that requires a specific API key scope
    
    Args:
        required_scope: The required scope (e.g., "campaigns:read")
        
    Returns:
        User: The authenticated user if scope is granted
        
    Raises:
        HTTPException: 403 if scope is not granted
    """
    user, api_key_obj = api_key_user
    
    if not await check_api_key_permission(api_key_obj, required_scope):
        logger.warning(f"API key {api_key_obj.id} attempted access without scope: {required_scope}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have required permission: {required_scope}",
        )
    
    return user


async def get_optional_user_from_api_key(
    api_key: Optional[str] = Security(api_key_header),
    request: Request = None,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional API key authentication for endpoints that work with or without auth
    
    Returns:
        Optional[User]: User object if valid API key provided, None otherwise
    """
    if not api_key:
        return None
    
    try:
        return await get_user_from_api_key(api_key, request, db)
    except HTTPException:
        return None


async def _log_api_key_usage(
    api_key_obj: ApiKey,
    request: Request,
    db: Session
) -> None:
    """
    Log API key usage for analytics and monitoring
    
    Args:
        api_key_obj: The API key object
        request: The FastAPI request object
        db: Database session
    """
    try:
        usage_record = ApiKeyUsage(
            api_key_id=api_key_obj.id,
            endpoint=request.url.path if request else None,
            method=request.method if request else None,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None,
            timestamp=datetime.utcnow()
        )
        
        db.add(usage_record)
        db.commit()
        
    except Exception as e:
        logger.error(f"Failed to log API key usage: {str(e)}")
        # Don't raise exception - usage logging shouldn't break the request
