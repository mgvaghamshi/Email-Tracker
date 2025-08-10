"""
Common dependencies for the EmailTracker API

DEPRECATED: This file contains legacy authentication dependencies.
New code should use:
- app.auth.jwt_auth for dashboard/frontend authentication
- app.auth.api_key_auth for external programmatic access

This file is kept for backward compatibility during the migration.
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Generator

from .database.connection import SessionLocal
from .database.user_models import ApiKey
from .database.user_models import User
from .core.security import verify_api_key, get_api_key_info
from .core.user_security import jwt_manager

# Import the new authentication dependencies
from .auth.jwt_auth import (
    get_current_user_from_jwt,
    get_current_active_user_from_jwt,
    get_current_verified_user_from_jwt,
    get_optional_user_from_jwt
)
from .auth.api_key_auth import (
    get_user_from_api_key,
    get_user_and_api_key,
    require_api_key_scope,
    get_optional_user_from_api_key
)

security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_admin_user(
    current_user: User = Depends(get_current_active_user_from_jwt),
    db: Session = Depends(get_db)
) -> User:
    """Get current user with admin permissions"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required"
        )
    
    from .core.user_security import require_permission
    require_permission(current_user, "admin:read", db)
    return current_user


# ============================================================================
# LEGACY API KEY DEPENDENCIES (DEPRECATED)
# Use app.auth.api_key_auth instead
# ============================================================================

# ============================================================================
# LEGACY API KEY DEPENDENCIES (DEPRECATED)
# Use app.auth.api_key_auth instead
# ============================================================================

async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    DEPRECATED: Use get_user_from_api_key() instead
    Validate API key from Authorization header
    Expected format: Bearer <api_key>
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    api_key = credentials.credentials
    if not verify_api_key(api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return api_key


async def get_optional_api_key(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[str]:
    """
    DEPRECATED: Use get_optional_user_from_api_key() instead
    Optional API key validation for public endpoints that can work with or without auth
    """
    if not credentials:
        return None
    
    try:
        return await get_api_key(credentials)
    except HTTPException:
        return None


async def get_current_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> ApiKey:
    """
    DEPRECATED: Use get_user_and_api_key() instead
    Get the current API key object from the database
    """
    api_key_string = await get_api_key(credentials)
    
    # Look up the API key in the database
    api_key = get_api_key_info(api_key_string)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return api_key


# ============================================================================
# LEGACY AUTHENTICATION DEPENDENCIES (DEPRECATED)
# Use app.auth.jwt_auth and app.auth.api_key_auth instead
# ============================================================================

# Legacy function aliases for backward compatibility
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """DEPRECATED: Use get_current_user_from_jwt instead"""
    return await get_current_user_from_jwt(credentials, db)


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """DEPRECATED: Use get_current_active_user_from_jwt instead"""
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """DEPRECATED: Use get_current_verified_user_from_jwt instead"""
    return await get_current_verified_user_from_jwt.__wrapped__(current_user)


# ============================================================================
# UNIFIED AUTHENTICATION (JWT or API Key) - For routes that support both
# ============================================================================

async def get_authenticated_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get authenticated user from either JWT token or API key.
    
    Tries JWT first (Authorization: Bearer <token>), then falls back to
    treating the token as an API key for backward compatibility.
    
    NEW CODE SHOULD USE SPECIFIC AUTH METHODS:
    - get_current_user_from_jwt() for dashboard routes
    - get_user_from_api_key() for external API routes
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try JWT token first (dashboard user authentication)
    try:
        result = jwt_manager.verify_access_token(token, db)
        if result:
            user, session = result
            if user.is_active:
                return user
    except Exception:
        pass  # Fall through to API key authentication
    
    # Try API key authentication (programmatic access)
    try:
        api_key_obj = get_api_key_info(token)
        if api_key_obj and api_key_obj.is_active and api_key_obj.user_id:
            user = db.query(User).filter(User.id == api_key_obj.user_id).first()
            if user and user.is_active:
                return user
    except Exception:
        pass
    
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

# ============================================================================
# END OF LEGACY DEPENDENCIES
# 
# FOR NEW CODE, USE:
# - from app.auth.jwt_auth import get_current_user_from_jwt
# - from app.auth.api_key_auth import get_user_from_api_key
# ============================================================================
