"""
Common dependencies for the EmailTracker API
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Generator

from .database.connection import SessionLocal
from .core.security import verify_api_key


security = HTTPBearer()


def get_db() -> Generator[Session, None, None]:
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
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
    Optional API key validation for public endpoints that can work with or without auth
    """
    if not credentials:
        return None
    
    try:
        return await get_api_key(credentials)
    except HTTPException:
        return None
