"""
Admin user management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from datetime import datetime, timedelta
import uuid

from ...db import SessionLocal
from ...database.user_models import User, UserSession, LoginAttempt, Role, UserRole, UserStatus
from ...schemas.users import (
    UserWithRolesResponse, UserUpdate, MessageResponse,
    UserStats, SecurityStats, RoleResponse
)
from ...auth.jwt_auth import get_current_superuser
from ...core.security import hash_password

router = APIRouter(prefix="/api/v1/admin", tags=["Admin - User Management"])


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/users", response_model=dict)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    role_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    List all users with filtering and pagination
    
    Returns a paginated list of users with their roles and permissions.
    """
    query = db.query(User)
    
    # Apply search filter
    if search:
        query = query.filter(
            or_(
                User.email.ilike(f"%{search}%"),
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%")
            )
        )
    
    # Apply status filter
    if status:
        if status == "active":
            query = query.filter(User.is_active == True, User.is_verified == True)
        elif status == "inactive":
            query = query.filter(User.is_active == False)
        elif status == "unverified":
            query = query.filter(User.is_verified == False)
        elif status == "locked":
            query = query.filter(User.locked_until.isnot(None))
    
    # Apply role filter
    if role_id:
        query = query.join(UserRole).filter(UserRole.role_id == role_id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    users = query.offset(skip).limit(limit).all()
    
    return {
        "users": users,
        "total": total,
        "page": skip // limit + 1,
        "page_size": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/users/{user_id}", response_model=UserWithRolesResponse)
async def get_user_details(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Get detailed user information
    
    Returns detailed information about a specific user including roles and permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/users/{user_id}", response_model=UserWithRolesResponse)
async def update_user(
    user_id: str,
    user_update: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Update user information (admin only)
    
    Updates user information including admin-only fields like active status.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update allowed fields
    for key, value in user_update.items():
        if value is not None and hasattr(user, key):
            setattr(user, key, value)
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Delete user account (admin only)
    
    Permanently deletes a user account and all associated data.
    """
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db.delete(user)
    db.commit()
    
    return MessageResponse(message="User deleted successfully")


@router.post("/users/{user_id}/unlock", response_model=MessageResponse)
async def unlock_user_account(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Unlock user account (admin only)
    
    Unlocks a user account that has been locked due to failed login attempts.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.unlock_account()
    db.commit()
    
    return MessageResponse(message="User account unlocked successfully")


@router.post("/users/{user_id}/revoke-sessions", response_model=MessageResponse)
async def revoke_user_sessions(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Revoke all user sessions (admin only)
    
    Revokes all active sessions for a user, forcing them to re-authenticate.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Revoke all sessions
    sessions = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False
    ).all()
    
    for session in sessions:
        session.is_revoked = True
        session.revoked_at = datetime.utcnow()
    
    db.commit()
    
    return MessageResponse(message=f"Revoked {len(sessions)} session(s)")


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def admin_reset_password(
    user_id: str,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Reset user password (admin only)
    
    Resets a user's password without requiring the old password.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_password = request.get("new_password")
    if not new_password or len(new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters"
        )
    
    user.password_hash = hash_password(new_password)
    user.updated_at = datetime.utcnow()
    db.commit()
    
    return MessageResponse(message="Password reset successfully")


@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    List all roles
    
    Returns a list of all available roles in the system.
    """
    roles = db.query(Role).all()
    return roles


@router.post("/users/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def assign_role_to_user(
    user_id: str,
    role_id: str,
    expires_at: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Assign role to user (admin only)
    
    Assigns a role to a user with optional expiration.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if already assigned
    existing = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Role already assigned to user")
    
    user_role = UserRole(
        id=str(uuid.uuid4()),
        user_id=user_id,
        role_id=role_id,
        expires_at=expires_at
    )
    db.add(user_role)
    db.commit()
    
    return MessageResponse(message=f"Role '{role.name}' assigned to user")


@router.delete("/users/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Remove role from user (admin only)
    
    Removes a role assignment from a user.
    """
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id
    ).first()
    
    if not user_role:
        raise HTTPException(status_code=404, detail="Role assignment not found")
    
    db.delete(user_role)
    db.commit()
    
    return MessageResponse(message="Role removed from user")


@router.get("/stats/users", response_model=UserStats)
async def get_user_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Get user statistics
    
    Returns various statistics about users in the system.
    """
    total_users = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(
        User.is_active == True,
        User.is_verified == True
    ).scalar()
    inactive_users = db.query(func.count(User.id)).filter(
        User.is_active == False
    ).scalar()
    unverified_users = db.query(func.count(User.id)).filter(
        User.is_verified == False
    ).scalar()
    
    # New users in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = db.query(func.count(User.id)).filter(
        User.created_at >= thirty_days_ago
    ).scalar()
    
    return UserStats(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        unverified_users=unverified_users,
        new_users_30d=new_users_30d
    )


@router.get("/stats/security", response_model=SecurityStats)
async def get_security_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_superuser)
):
    """
    Get security-related statistics
    
    Returns statistics about security events and account status.
    """
    locked_accounts = db.query(func.count(User.id)).filter(
        User.locked_until.isnot(None)
    ).scalar()
    
    # Failed login attempts in last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    failed_logins_24h = db.query(func.count(LoginAttempt.id)).filter(
        LoginAttempt.success == False,
        LoginAttempt.attempted_at >= twenty_four_hours_ago
    ).scalar()
    
    # Suspicious activities (marked as suspicious)
    suspicious_activities = db.query(func.count(LoginAttempt.id)).filter(
        LoginAttempt.is_suspicious == True,
        LoginAttempt.attempted_at >= twenty_four_hours_ago
    ).scalar()
    
    # 2FA enabled users
    two_factor_enabled = db.query(func.count(User.id)).filter(
        User.two_factor_enabled == True
    ).scalar()
    
    return SecurityStats(
        locked_accounts=locked_accounts,
        failed_logins_24h=failed_logins_24h,
        suspicious_activities=suspicious_activities,
        two_factor_enabled=two_factor_enabled
    )
