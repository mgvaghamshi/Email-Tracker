"""
JWT-based authentication for dashboard frontend users

Handles login, token verification, and user session management for the web dashboard.
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from ..database.connection import get_db
from ..database.user_models import User
from ..core.user_security import jwt_manager
from ..core.logging_config import get_logger
from .middleware import AuthConfig, require_verified_user, require_active_user

logger = get_logger("auth.jwt_auth")
security = HTTPBearer()


async def get_current_user_from_jwt(
    credentials: HTTPAuthorizationCredentials = Security(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token (for dashboard routes)
    
    Expected header: Authorization: Bearer <JWT_TOKEN>
    
    Returns:
        User: The authenticated user object
        
    Raises:
        HTTPException: 401 if token is invalid, expired, or user is inactive
    """
    if not credentials:
        logger.warning("❌ JWT authentication failed: No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AuthConfig.get_error_messages()["jwt_required"],
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    logger.debug(f"🔑 JWT token received: {credentials.credentials[:10]}...{credentials.credentials[-10:] if len(credentials.credentials) > 20 else '***'}")
    
    try:
        # Verify JWT token
        result = jwt_manager.verify_access_token(credentials.credentials, db)
        if not result:
            logger.warning("❌ JWT authentication failed: Token verification failed")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=AuthConfig.get_error_messages()["jwt_invalid"],
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user, session = result
        
        # Check if user is active
        require_active_user(user)
        
        logger.info(f"✅ JWT authentication successful for user: {user.email}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ JWT authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AuthConfig.get_error_messages()["jwt_invalid"],
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user_from_jwt(
    current_user: User = Depends(get_current_user_from_jwt)
) -> User:
    """
    Get current active user from JWT (convenience wrapper)
    
    Returns:
        User: The authenticated active user
    """
    return current_user


async def get_current_verified_user_from_jwt(
    current_user: User = Depends(get_current_active_user_from_jwt)
) -> User:
    """
    Get current verified user from JWT (email verification required)
    
    Returns:
        User: The authenticated verified user
        
    Raises:
        HTTPException: 400 if user email is not verified
    """
    require_verified_user(current_user)
    return current_user


async def get_optional_user_from_jwt(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Optional JWT authentication for endpoints that work with or without auth
    
    Returns:
        Optional[User]: User object if valid token provided, None otherwise
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user_from_jwt(credentials, db)
    except HTTPException:
        return None
