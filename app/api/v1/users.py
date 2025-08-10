"""
User management and authentication endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import json
import json

from ...dependencies import get_db
from ...core.user_security import (
    hash_password, verify_password, authenticate_user, create_user_session, jwt_manager,
    revoke_session, revoke_all_user_sessions, record_login_attempt,
    check_account_lockout, unlock_account, create_password_reset,
    verify_reset_token, create_email_verification, verify_email_token,
    get_user_permissions, has_permission, require_permission
)
from ...database.user_models import User, UserSession, Role, UserRole, ApiKey, SCOPE_PRESETS
from ...core.logging_config import get_logger
from ...config import settings

logger = get_logger("api.users")
from ...schemas.user import (
    UserCreate, UserResponse, UserUpdate, LoginRequest, LoginResponse,
    RefreshTokenRequest, RefreshTokenResponse, PasswordChangeRequest,
    PasswordResetRequest, PasswordResetConfirm, EmailVerificationRequest,
    EmailVerificationConfirm, SessionListResponse, SessionResponse,
    UserWithRolesResponse, MessageResponse, SuccessResponse,
    UserListFilter, UserListResponse, UserAdminUpdate
)

router = APIRouter(prefix="/users", tags=["User Management"])
security = HTTPBearer()


# ============================================================================
# Authentication Dependencies
# ============================================================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    result = jwt_manager.verify_access_token(credentials.credentials, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user, session = result
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current verified user"""
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email verification required"
        )
    return current_user


async def get_admin_user(
    current_user: User = Depends(get_current_verified_user),
    db: Session = Depends(get_db)
) -> User:
    """Get current user with admin permissions"""
    require_permission(current_user, "admin:read", db)
    return current_user


# ============================================================================
# Authentication Endpoints
# ============================================================================

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Register a new user account
    
    Creates a new user account with email verification required.
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    hashed_password = hash_password(user_data.password)
    
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        timezone=user_data.timezone,
        locale=user_data.locale,
        is_verified=settings.is_development  # Auto-verify in development
    )
    
    # Set full name
    if user_data.first_name and user_data.last_name:
        user.full_name = f"{user_data.first_name} {user_data.last_name}"
    elif user_data.first_name:
        user.full_name = user_data.first_name
    elif user_data.last_name:
        user.full_name = user_data.last_name
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Log auto-verification in development
    if settings.is_development and user.is_verified:
        logger.info(f"User {user.email} auto-verified in development mode")
    
    # Create email verification (still needed for production)
    verification, token = create_email_verification(
        user=user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        db=db
    )
    
    # TODO: Send verification email with token
    # For now, just return success
    
    return UserResponse.from_orm(user)


@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> LoginResponse:
    """
    Authenticate user and create session
    
    Returns JWT access and refresh tokens for the user.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Check account lockout
    is_locked, locked_until = check_account_lockout(login_data.email, db)
    if is_locked:
        record_login_attempt(
            email=login_data.email,
            success=False,
            failure_reason="account_locked",
            ip_address=ip_address,
            user_agent=user_agent,
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Account locked until {locked_until}"
        )
    
    # Authenticate user
    user = authenticate_user(login_data.email, login_data.password, db)
    if not user:
        record_login_attempt(
            email=login_data.email,
            success=False,
            failure_reason="invalid_credentials",
            ip_address=ip_address,
            user_agent=user_agent,
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Create session
    session, access_token, refresh_token = create_user_session(
        user=user,
        device_info=login_data.device_info,
        ip_address=ip_address,
        user_agent=user_agent,
        remember_me=login_data.remember_me,
        db=db
    )
    
    # Update last login
    user.last_login_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    
    db.commit()
    
    # Record successful login
    record_login_attempt(
        email=login_data.email,
        success=True,
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user.id,
        db=db
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=30 * 60,  # 30 minutes
        user=UserResponse.from_orm(user)
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
) -> RefreshTokenResponse:
    """
    Refresh access token using refresh token
    
    Returns a new access token if the refresh token is valid.
    """
    result = jwt_manager.verify_refresh_token(refresh_data.refresh_token, db)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    user, session = result
    
    # Create new access token
    access_token = jwt_manager.create_access_token(
        user_id=user.id,
        session_id=session.id
    )
    
    # Update session access token JTI
    access_payload = jwt_manager.decode_token(access_token)
    session.access_token_jti = access_payload["jti"]
    session.last_activity = datetime.utcnow()
    db.commit()
    
    return RefreshTokenResponse(
        access_token=access_token,
        expires_in=30 * 60  # 30 minutes
    )


@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Logout user and revoke session
    
    Revokes the current session and invalidates tokens.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    result = jwt_manager.verify_access_token(credentials.credentials, db)
    if result:
        user, session = result
        revoke_session(session.id, "logout", db)
    
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Logout from all sessions
    
    Revokes all user sessions except optionally the current one.
    """
    current_session_id = None
    result = jwt_manager.verify_access_token(credentials.credentials, db)
    if result:
        user, session = result
        current_session_id = session.id
    
    count = revoke_all_user_sessions(current_user.id, current_session_id, db)
    
    return MessageResponse(
        message=f"Successfully logged out from {count} sessions"
    )


# ============================================================================
# User Profile Endpoints
# ============================================================================

@router.get("/me", response_model=UserWithRolesResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserWithRolesResponse:
    """
    Get current user profile
    
    Returns the current user's profile information including roles and permissions.
    """
    # Get user roles and convert them properly
    roles_data = []
    for user_role in current_user.user_roles:
        if user_role.is_active and user_role.role.is_active:
            if user_role.expires_at is None or user_role.expires_at > datetime.utcnow():
                role = user_role.role
                # Convert permissions from JSON string to list
                permissions_list = []
                if role.permissions:
                    import json
                    permissions_list = json.loads(role.permissions)
                
                role_data = {
                    "id": role.id,
                    "name": role.name,
                    "display_name": role.display_name,
                    "description": role.description,
                    "permissions": permissions_list,
                    "is_active": role.is_active,
                    "is_system": role.is_system,
                    "created_at": role.created_at,
                    "updated_at": role.updated_at
                }
                roles_data.append(role_data)
    
    # Get permissions
    permissions = get_user_permissions(current_user, db)
    
    user_response = UserResponse.from_orm(current_user)
    return UserWithRolesResponse(
        **user_response.dict(),
        roles=roles_data,
        permissions=permissions
    )


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> UserResponse:
    """
    Update current user profile
    
    Updates the current user's profile information.
    """
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "preferences":
            setattr(current_user, field, json.dumps(value) if value else None)
        else:
            setattr(current_user, field, value)
    
    # Update full name if first_name or last_name changed
    if "first_name" in update_data or "last_name" in update_data:
        if current_user.first_name and current_user.last_name:
            current_user.full_name = f"{current_user.first_name} {current_user.last_name}"
        elif current_user.first_name:
            current_user.full_name = current_user.first_name
        elif current_user.last_name:
            current_user.full_name = current_user.last_name
        else:
            current_user.full_name = None
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    return UserResponse.from_orm(current_user)


# ============================================================================
# Password Management Endpoints
# ============================================================================

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Change user password
    
    Changes the current user's password after verifying the current password.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.password_hash = hash_password(password_data.new_password)
    current_user.password_changed_at = datetime.utcnow()
    current_user.updated_at = datetime.utcnow()
    db.commit()
    
    # Revoke all other sessions for security
    revoke_all_user_sessions(current_user.id, db=db)
    
    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request_data: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Request password reset
    
    Sends a password reset email to the user if the email exists.
    """
    user = db.query(User).filter(User.email == request_data.email).first()
    if user:
        # Create password reset token
        reset, token = create_password_reset(
            user=user,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            db=db
        )
        
        # TODO: Send password reset email with token
        # For now, just create the token
    
    # Always return success to prevent email enumeration
    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Reset password using token
    
    Resets the user's password using a valid reset token.
    """
    # Verify reset token
    reset = verify_reset_token(reset_data.token, db)
    if not reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = hash_password(reset_data.new_password)
    user.password_changed_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    
    # Mark reset as used
    reset.is_used = True
    reset.used_at = datetime.utcnow()
    
    db.commit()
    
    # Revoke all sessions for security
    revoke_all_user_sessions(user.id, db=db)
    
    return MessageResponse(message="Password reset successfully")


# ============================================================================
# Email Verification Endpoints
# ============================================================================

@router.post("/verify-email", response_model=MessageResponse)
async def request_email_verification(
    request: Request,
    request_data: EmailVerificationRequest = EmailVerificationRequest(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Request email verification
    
    Sends an email verification link to the user's email.
    """
    email_to_verify = request_data.email or current_user.email
    
    # Create verification token
    verification, token = create_email_verification(
        user=current_user,
        email=email_to_verify,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        db=db
    )
    
    # TODO: Send verification email with token
    # For now, just create the token
    
    return MessageResponse(
        message=f"Verification email sent to {email_to_verify}"
    )


@router.post("/verify-email/confirm", response_model=MessageResponse)
async def confirm_email_verification(
    confirm_data: EmailVerificationConfirm,
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Confirm email verification
    
    Verifies the user's email using a valid verification token.
    """
    # Verify token
    verification = verify_email_token(confirm_data.token, db)
    if not verification:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Get user
    user = db.query(User).filter(User.id == verification.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user
    if verification.email == user.email:
        user.is_verified = True
        user.email_verified_at = datetime.utcnow()
    
    user.updated_at = datetime.utcnow()
    
    # Mark verification as used
    verification.is_used = True
    verification.verified_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message="Email verified successfully")


# ============================================================================
# Session Management Endpoints
# ============================================================================

@router.get("/sessions", response_model=SessionListResponse)
async def list_user_sessions(
    current_user: User = Depends(get_current_active_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> SessionListResponse:
    """
    List user sessions
    
    Returns a list of all active sessions for the current user.
    """
    # Get current session ID
    current_session_id = None
    result = jwt_manager.verify_access_token(credentials.credentials, db)
    if result:
        user, session = result
        current_session_id = session.id
    
    # Get all active sessions
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).order_by(UserSession.last_activity.desc()).all()
    
    session_responses = []
    for session in sessions:
        device_info = json.loads(session.device_info) if session.device_info else None
        session_responses.append(SessionResponse(
            id=session.id,
            device_info=device_info,
            ip_address=session.ip_address,
            location=session.location,
            is_current=(session.id == current_session_id),
            created_at=session.created_at,
            last_activity=session.last_activity,
            expires_at=session.expires_at
        ))
    
    return SessionListResponse(
        sessions=session_responses,
        current_session_id=current_session_id or ""
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_user_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Revoke a user session
    
    Revokes a specific session for the current user.
    """
    # Verify session belongs to user
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    revoke_session(session_id, "user_revoked", db)
    
    return MessageResponse(message="Session revoked successfully")


# ============================================================================
# API Key Management
# ============================================================================

@router.get("/me/api-keys")
async def get_user_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's API keys (without exposing the actual key values)"""
    api_keys = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active == True,
        ApiKey.revoked == False
    ).all()
    
    return [
        {
            "id": key.id,
            "name": key.name,
            "prefix": key.prefix,
            "scopes": json.loads(key.scopes) if key.scopes else [],
            "created_at": key.created_at,
            "last_used_at": key.last_used_at,
            "usage_count": key.usage_count,
            "requests_per_minute": key.requests_per_minute,
            "requests_per_day": key.requests_per_day
        }
        for key in api_keys
    ]

# ============================================================================
# END OF FILE
# ============================================================================
