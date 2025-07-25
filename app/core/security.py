"""
Security utilities for API key management and authentication
"""
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from ..database.connection import SessionLocal
from ..database.models import ApiKey


def generate_api_key() -> Tuple[str, str]:
    """
    Generate a new API key and return both the key and its hash
    Returns: (api_key, api_key_hash)
    """
    # Generate a secure random API key
    api_key = f"et_{secrets.token_urlsafe(32)}"  # et_ prefix for EmailTracker
    
    # Hash the API key for storage
    api_key_hash = hash_api_key(api_key)
    
    return api_key, api_key_hash


def hash_api_key(api_key: str) -> str:
    """Hash an API key for secure storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(api_key: str) -> bool:
    """
    Verify if an API key is valid and active
    """
    if not api_key:
        return False
    
    # Hash the provided key
    api_key_hash = hash_api_key(api_key)
    
    # Check against database
    db = SessionLocal()
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.key_hash == api_key_hash,
            ApiKey.is_active == True
        ).first()
        
        if not api_key_record:
            return False
        
        # Check if key has expired
        if api_key_record.expires_at and api_key_record.expires_at < datetime.utcnow():
            return False
        
        # Update last used timestamp
        api_key_record.last_used_at = datetime.utcnow()
        db.commit()
        
        return True
        
    except Exception:
        return False
    finally:
        db.close()


def get_api_key_info(api_key: str) -> Optional[ApiKey]:
    """
    Get API key information
    """
    if not api_key:
        return None
    
    api_key_hash = hash_api_key(api_key)
    
    db = SessionLocal()
    try:
        return db.query(ApiKey).filter(
            ApiKey.key_hash == api_key_hash,
            ApiKey.is_active == True
        ).first()
    finally:
        db.close()


def create_api_key(
    name: str,
    user_id: Optional[str] = None,
    requests_per_minute: int = 100,
    requests_per_day: int = 10000,
    expires_in_days: Optional[int] = None
) -> Tuple[str, ApiKey]:
    """
    Create a new API key
    Returns: (api_key_string, api_key_record)
    """
    api_key, api_key_hash = generate_api_key()
    
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    db = SessionLocal()
    try:
        api_key_record = ApiKey(
            key_hash=api_key_hash,
            name=name,
            user_id=user_id,
            requests_per_minute=requests_per_minute,
            requests_per_day=requests_per_day,
            expires_at=expires_at
        )
        
        db.add(api_key_record)
        db.commit()
        db.refresh(api_key_record)
        
        return api_key, api_key_record
        
    finally:
        db.close()


def revoke_api_key(api_key: str) -> bool:
    """
    Revoke an API key (mark as inactive)
    """
    api_key_hash = hash_api_key(api_key)
    
    db = SessionLocal()
    try:
        api_key_record = db.query(ApiKey).filter(
            ApiKey.key_hash == api_key_hash
        ).first()
        
        if api_key_record:
            api_key_record.is_active = False
            db.commit()
            return True
        
        return False
        
    finally:
        db.close()


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verify webhook signature for secure webhook delivery
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
