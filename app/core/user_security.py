"""
JWT token and user authentication utilities
"""
import hashlib
import secrets
import hmac
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from uuid import uuid4
from sqlalchemy.orm import Session
import bcrypt
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
import json

from ..database.connection import SessionLocal
from ..database.user_models import User, UserSession, PasswordReset, EmailVerification, LoginAttempt
from ..config import settings


# ============================================================================
# Password Security
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


# ============================================================================
# JWT Token Management
# ============================================================================

class JWTManager:
    """JWT token management class"""
    
    def __init__(self):
        self.secret_key = settings.secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 30
    
    def create_access_token(
        self, 
        user_id: str, 
        session_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        # Generate unique JWT ID
        jti = secrets.token_urlsafe(32)
        
        to_encode = {
            "sub": user_id,  # Subject (user ID)
            "session_id": session_id,
            "jti": jti,  # JWT ID for token revocation
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        user_id: str, 
        session_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT refresh token"""
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        # Generate unique JWT ID
        jti = secrets.token_urlsafe(32)
        
        to_encode = {
            "sub": user_id,  # Subject (user ID)
            "session_id": session_id,
            "jti": jti,  # JWT ID for token revocation
            "type": "refresh",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def decode_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except ExpiredSignatureError:
            return None
        except InvalidTokenError:
            return None
    
    def verify_access_token(self, token: str, db: Session) -> Optional[Tuple[User, UserSession]]:
        """Verify an access token and return user and session"""
        payload = self.decode_token(token)
        if not payload or payload.get("type") != "access":
            return None
        
        user_id = payload.get("sub")
        session_id = payload.get("session_id")
        jti = payload.get("jti")
        
        if not user_id or not session_id or not jti:
            return None
        
        # Check if session exists and is active
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.access_token_jti == jti,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        # Get user
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        
        if not user:
            return None
        
        # Update last activity
        session.last_activity = datetime.utcnow()
        db.commit()
        
        return user, session
    
    def verify_refresh_token(self, token: str, db: Session) -> Optional[Tuple[User, UserSession]]:
        """Verify a refresh token and return user and session"""
        payload = self.decode_token(token)
        if not payload or payload.get("type") != "refresh":
            return None
        
        user_id = payload.get("sub")
        session_id = payload.get("session_id")
        jti = payload.get("jti")
        
        if not user_id or not session_id or not jti:
            return None
        
        # Check if session exists and is active
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == user_id,
            UserSession.refresh_token_jti == jti,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            return None
        
        # Get user
        user = db.query(User).filter(
            User.id == user_id,
            User.is_active == True
        ).first()
        
        if not user:
            return None
        
        return user, session


# Create global JWT manager instance
jwt_manager = JWTManager()


# ============================================================================
# Session Management
# ============================================================================

def create_user_session(
    user: User,
    device_info: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    location: Optional[str] = None,
    remember_me: bool = False,
    db: Session = None
) -> Tuple[UserSession, str, str]:
    """
    Create a new user session with JWT tokens
    Returns: (session, access_token, refresh_token)
    """
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        # Create JWT tokens first
        access_token_expires = timedelta(minutes=30)
        refresh_token_expires = timedelta(days=30 if remember_me else 7)
        
        # We need to create a temporary session ID for the tokens
        temp_session_id = str(uuid4())
        
        access_token = jwt_manager.create_access_token(
            user_id=user.id,
            session_id=temp_session_id,
            expires_delta=access_token_expires
        )
        
        refresh_token = jwt_manager.create_refresh_token(
            user_id=user.id,
            session_id=temp_session_id,
            expires_delta=refresh_token_expires
        )
        
        # Extract JTIs from tokens
        access_payload = jwt_manager.decode_token(access_token)
        refresh_payload = jwt_manager.decode_token(refresh_token)
        
        # Create session record with JTIs
        session = UserSession(
            id=temp_session_id,  # Use the same ID we used in tokens
            user_id=user.id,
            access_token_jti=access_payload["jti"],
            refresh_token_jti=refresh_payload["jti"],
            device_info=json.dumps(device_info) if device_info else None,
            ip_address=ip_address,
            user_agent=user_agent,
            location=location,
            expires_at=datetime.utcnow() + timedelta(
                days=30 if remember_me else 7
            )
        )
        
        db.add(session)
        db.commit()
        
        return session, access_token, refresh_token
        
    finally:
        if close_db:
            db.close()


def revoke_session(session_id: str, reason: str = "logout", db: Session = None) -> bool:
    """Revoke a user session"""
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        session = db.query(UserSession).filter(UserSession.id == session_id).first()
        if session:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revoked_reason = reason
            db.commit()
            return True
        return False
        
    finally:
        if close_db:
            db.close()


def revoke_all_user_sessions(user_id: str, except_session_id: Optional[str] = None, db: Session = None) -> int:
    """Revoke all sessions for a user, optionally except one"""
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        query = db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_active == True
        )
        
        if except_session_id:
            query = query.filter(UserSession.id != except_session_id)
        
        sessions = query.all()
        count = len(sessions)
        
        for session in sessions:
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revoked_reason = "revoke_all"
        
        db.commit()
        return count
        
    finally:
        if close_db:
            db.close()


# ============================================================================
# User Security Functions
# ============================================================================

def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
    """Authenticate a user with email and password"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return None
    
    if not verify_password(password, user.password_hash):
        return None
    
    if not user.is_active:
        return None
    
    return user


def record_login_attempt(
    email: str, 
    success: bool, 
    failure_reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    user_id: Optional[str] = None,
    db: Session = None
) -> None:
    """Record a login attempt for security tracking"""
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        attempt = LoginAttempt(
            email=email,
            success=success,
            failure_reason=failure_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            user_id=user_id
        )
        
        db.add(attempt)
        db.commit()
        
    finally:
        if close_db:
            db.close()


def check_account_lockout(email: str, db: Session) -> Tuple[bool, Optional[datetime]]:
    """Check if account is locked due to failed login attempts"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return False, None
    
    # Check if account is currently locked
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True, user.locked_until
    
    # Check recent failed attempts
    failed_attempts = db.query(LoginAttempt).filter(
        LoginAttempt.email == email,
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= datetime.utcnow() - timedelta(hours=1)
    ).count()
    
    # Lock account if too many failed attempts
    if failed_attempts >= 5:
        user.locked_until = datetime.utcnow() + timedelta(hours=1)
        user.failed_login_attempts = failed_attempts
        db.commit()
        return True, user.locked_until
    
    return False, None


def unlock_account(email: str, db: Session) -> bool:
    """Unlock a user account"""
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        return False
    
    user.locked_until = None
    user.failed_login_attempts = 0
    db.commit()
    
    return True


# ============================================================================
# Password Reset Functions
# ============================================================================

def generate_reset_token() -> Tuple[str, str]:
    """Generate a password reset token and its hash"""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def create_password_reset(
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Session = None
) -> Tuple[PasswordReset, str]:
    """Create a password reset request"""
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        token, token_hash = generate_reset_token()
        
        # Invalidate existing password reset requests
        db.query(PasswordReset).filter(
            PasswordReset.user_id == user.id,
            PasswordReset.is_used == False
        ).update({"is_used": True})
        
        # Create new password reset
        reset = PasswordReset(
            user_id=user.id,
            token_hash=token_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        )
        
        db.add(reset)
        db.commit()
        
        return reset, token
        
    finally:
        if close_db:
            db.close()


def verify_reset_token(token: str, db: Session) -> Optional[PasswordReset]:
    """Verify a password reset token"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    reset = db.query(PasswordReset).filter(
        PasswordReset.token_hash == token_hash,
        PasswordReset.is_used == False,
        PasswordReset.expires_at > datetime.utcnow()
    ).first()
    
    return reset


# ============================================================================
# Email Verification Functions
# ============================================================================

def generate_verification_token() -> Tuple[str, str]:
    """Generate an email verification token and its hash"""
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def create_email_verification(
    user: User,
    email: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    db: Session = None
) -> Tuple[EmailVerification, str]:
    """Create an email verification request"""
    if not db:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        token, token_hash = generate_verification_token()
        email_to_verify = email or user.email
        
        # Invalidate existing verification requests for this email
        db.query(EmailVerification).filter(
            EmailVerification.user_id == user.id,
            EmailVerification.email == email_to_verify,
            EmailVerification.is_used == False
        ).update({"is_used": True})
        
        # Create new email verification
        verification = EmailVerification(
            user_id=user.id,
            token_hash=token_hash,
            email=email_to_verify,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(hours=24)  # 24 hour expiry
        )
        
        db.add(verification)
        db.commit()
        
        return verification, token
        
    finally:
        if close_db:
            db.close()


def verify_email_token(token: str, db: Session) -> Optional[EmailVerification]:
    """Verify an email verification token"""
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    verification = db.query(EmailVerification).filter(
        EmailVerification.token_hash == token_hash,
        EmailVerification.is_used == False,
        EmailVerification.expires_at > datetime.utcnow()
    ).first()
    
    return verification


# ============================================================================
# Utility Functions
# ============================================================================

def get_user_permissions(user: User, db: Session) -> List[str]:
    """Get all permissions for a user based on their roles"""
    permissions = set()
    
    for user_role in user.user_roles:
        if user_role.is_active and user_role.role.is_active:
            if user_role.expires_at is None or user_role.expires_at > datetime.utcnow():
                role_permissions = json.loads(user_role.role.permissions or "[]")
                permissions.update(role_permissions)
    
    # Superusers get all permissions
    if user.is_superuser:
        permissions.update([
            "admin:read", "admin:write", "admin:delete",
            "users:read", "users:write", "users:delete",
            "roles:read", "roles:write", "roles:delete",
            "api_keys:read", "api_keys:write", "api_keys:delete",
            "campaigns:read", "campaigns:write", "campaigns:delete",
            "contacts:read", "contacts:write", "contacts:delete",
            "templates:read", "templates:write", "templates:delete",
            "analytics:read", "settings:read", "settings:write"
        ])
    
    return list(permissions)


def has_permission(user: User, permission: str, db: Session) -> bool:
    """Check if user has a specific permission"""
    user_permissions = get_user_permissions(user, db)
    return permission in user_permissions


def require_permission(user: User, permission: str, db: Session) -> bool:
    """Require user to have a specific permission, raise exception if not"""
    if not has_permission(user, permission, db):
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission required: {permission}"
        )
    return True
