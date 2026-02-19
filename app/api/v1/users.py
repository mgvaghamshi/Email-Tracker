"""
User authentication and management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from ...db import SessionLocal
from ...database.user_models import User, UserSession, LoginAttempt, Role, UserRole, UserStatus
from ...schemas.users import (
    UserCreate, UserResponse, LoginRequest, LoginResponse,
    RefreshTokenRequest, RefreshTokenResponse, UserUpdate,
    PasswordChangeRequest, PasswordResetRequest, PasswordResetConfirm,
    EmailVerificationRequest, EmailVerificationConfirm,
    SessionResponse, SessionListResponse, MessageResponse,
    UserWithRolesResponse, RoleResponse
)
from ...auth.jwt_auth import (
    get_current_user, get_current_user, get_db
)
from ...core.security import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
    generate_random_token
)
from ...core.device_detection import get_device_info

router = APIRouter(prefix="/api/v1/users", tags=["User Management"])


# ============= Registration & Login =============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new user account
    
    Creates a new user account with email verification required.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if username already exists (if provided)
    if user_data.username:
        existing_username = db.query(User).filter(User.username == user_data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Create new user
    new_user = User(
        id=str(uuid.uuid4()),
        email=user_data.email,
        username=user_data.username,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        is_active=True,
        is_verified=False,
        is_superuser=False,
        status=UserStatus.ACTIVE,
        created_at=datetime.utcnow()
    )
    
    # Generate email verification token
    verification_token = generate_random_token()
    new_user.email_verification_token = verification_token
    new_user.email_verification_sent_at = datetime.utcnow()
    
    db.add(new_user)
    
    # Assign default role
    default_role = db.query(Role).filter(Role.is_default == True).first()
    if default_role:
        user_role = UserRole(
            id=str(uuid.uuid4()),
            user_id=new_user.id,
            role_id=default_role.id,
            assigned_at=datetime.utcnow()
        )
        db.add(user_role)
    
    db.commit()
    db.refresh(new_user)
    
    # TODO: Send verification email
    
    return new_user


@router.post("/login", response_model=LoginResponse)
async def login_user(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and create session
    
    Returns JWT access and refresh tokens for the user.
    """
    # Find user by email
    user = db.query(User).filter(User.email == login_data.email).first()
    
    # Get device info
    device_info = get_device_info(request)
    
    # Log login attempt
    attempt = LoginAttempt(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        email=login_data.email,
        success=False,
        ip_address=device_info.get("ip_address"),
        user_agent=device_info.get("user_agent"),
        device_type=device_info.get("device_type"),
        browser=device_info.get("browser"),
        os=device_info.get("os"),
        attempted_at=datetime.utcnow()
    )
    
    # Validate user and password
    if not user:
        attempt.failure_reason = "User not found"
        db.add(attempt)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if account is locked
    if user.is_locked():
        attempt.failure_reason = "Account locked"
        db.add(attempt)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is temporarily locked due to multiple failed login attempts"
        )
    
    # Verify password
    if not verify_password(login_data.password, user.hashed_password):
        # Increment failed attempts
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= 5:
            user.lock_account(duration_minutes=30)
        
        attempt.failure_reason = "Invalid password"
        db.add(attempt)
        db.commit()
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        attempt.failure_reason = "Account inactive"
        db.add(attempt)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Successful login
    attempt.success = True
    attempt.user_id = user.id
    db.add(attempt)
    
    # Reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    
    # Create session
    token_data = {"sub": user.id, "session_id": str(uuid.uuid4())}
    
    access_token_expires = timedelta(minutes=30)
    if login_data.remember_me:
        refresh_token_expires = timedelta(days=30)
    else:
        refresh_token_expires = timedelta(days=7)
    
    access_token = create_access_token(token_data, expires_delta=access_token_expires)
    refresh_token = create_refresh_token(token_data, expires_delta=refresh_token_expires)
    
    # Store session
    session = UserSession(
        id=token_data["session_id"],
        user_id=user.id,
        refresh_token=refresh_token,
        user_agent=device_info.get("user_agent"),
        ip_address=device_info.get("ip_address"),
        device_name=device_info.get("device_name"),
        device_type=device_info.get("device_type"),
        browser=device_info.get("browser"),
        os=device_info.get("os"),
        is_active=True,
        is_current=True,
        created_at=datetime.utcnow(),
        last_activity_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + refresh_token_expires
    )
    db.add(session)
    
    db.commit()
    db.refresh(user)
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        user=user
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    Returns a new access token if the refresh token is valid.
    """
    # Decode refresh token
    payload = decode_token(refresh_data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    session_id = payload.get("session_id")
    
    # Validate session
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == user_id,
        UserSession.refresh_token == refresh_data.refresh_token
    ).first()
    
    if not session or not session.is_valid():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )
    
    # Get user
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Create new access token
    token_data = {"sub": user.id, "session_id": session_id}
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(token_data, expires_delta=access_token_expires)
    
    # Update session activity
    session.last_activity_at = datetime.utcnow()
    db.commit()
    
    return RefreshTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


@router.post("/logout", response_model=MessageResponse)
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user and revoke session
    
    Revokes the current session and invalidates tokens.
    """
    # Get token from header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
        payload = decode_token(token)
        
        if payload:
            session_id = payload.get("session_id")
            if session_id:
                # Revoke session
                session = db.query(UserSession).filter(
                    UserSession.id == session_id,
                    UserSession.user_id == current_user.id
                ).first()
                
                if session:
                    session.is_active = False
                    session.revoked_at = datetime.utcnow()
                    db.commit()
    
    return MessageResponse(message="Successfully logged out")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout from all sessions
    
    Revokes all user sessions except optionally the current one.
    """
    # Revoke all sessions
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).update({
        "is_active": False,
        "revoked_at": datetime.utcnow()
    })
    
    db.commit()
    
    return MessageResponse(message="Successfully logged out from all devices")


# ============= Profile Management =============

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current user profile
    
    Returns the current user's profile information including roles and permissions.
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user profile
    
    Updates the current user's profile information.
    """
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
    
    if user_update.username is not None:
        # Check if username is taken
        existing = db.query(User).filter(
            User.username == user_update.username,
            User.id != current_user.id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        current_user.username = user_update.username
    
    current_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(current_user)
    
    return current_user


# ============= Password Management =============

@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    
    Changes the current user's password after verifying the current password.
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    current_user.require_password_change = False
    current_user.updated_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    reset_request: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset
    
    Sends a password reset email to the user if the email exists.
    """
    user = db.query(User).filter(User.email == reset_request.email).first()
    
    # Don't reveal if email exists or not
    if user:
        # Generate reset token
        reset_token = generate_random_token()
        user.password_reset_token = reset_token
        user.password_reset_sent_at = datetime.utcnow()
        user.password_reset_expires_at = datetime.utcnow() + timedelta(hours=1)
        
        db.commit()
        
        # TODO: Send password reset email
    
    return MessageResponse(
        message="If the email exists, a password reset link has been sent"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using token
    
    Resets the user's password using a valid reset token.
    """
    user = db.query(User).filter(
        User.password_reset_token == reset_data.token
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Check if token is expired
    if user.password_reset_expires_at and user.password_reset_expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired"
        )
    
    # Update password
    user.hashed_password = hash_password(reset_data.new_password)
    user.password_reset_token = None
    user.password_reset_sent_at = None
    user.password_reset_expires_at = None
    user.require_password_change = False
    user.updated_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message="Password reset successfully")


# ============= Email Verification =============

@router.post("/verify-email", response_model=MessageResponse)
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Request email verification
    
    Sends an email verification link to the user's email.
    """
    if current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )
    
    # Generate new verification token
    verification_token = generate_random_token()
    current_user.email_verification_token = verification_token
    current_user.email_verification_sent_at = datetime.utcnow()
    
    db.commit()
    
    # TODO: Send verification email
    
    return MessageResponse(message="Verification email sent")


@router.post("/verify-email/confirm", response_model=MessageResponse)
async def confirm_email_verification(
    confirm_data: EmailVerificationConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm email verification
    
    Verifies the user's email using a valid verification token.
    """
    user = db.query(User).filter(
        User.email_verification_token == confirm_data.token
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token"
        )
    
    # Mark email as verified
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    user.email_verification_token = None
    
    db.commit()
    
    return MessageResponse(message="Email verified successfully")


# ============= Session Management =============

@router.get("/sessions", response_model=SessionListResponse)
async def list_user_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List user sessions
    
    Returns a list of all active sessions for the current user.
    """
    sessions = db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).order_by(UserSession.last_activity_at.desc()).all()
    
    return SessionListResponse(
        sessions=sessions,
        total=len(sessions)
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_user_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a user session
    
    Revokes a specific session for the current user.
    """
    session = db.query(UserSession).filter(
        UserSession.id == session_id,
        UserSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    session.is_active = False
    session.revoked_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message="Session revoked successfully")


# ============= API Key Access =============

@router.get("/me/api-keys")
async def get_user_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's API keys (without exposing the actual key values)"""
    # TODO: Implement when API key models are ready
    return {"message": "API keys endpoint - to be implemented"}
