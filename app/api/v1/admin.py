"""
Admin endpoints for user and role management
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from typing import List, Optional
from datetime import datetime, timedelta
import json
import math

from ...dependencies import get_db, get_admin_user
from ...database.user_models import User, Role, UserRole, LoginAttempt, UserSession
from ...schemas.user import (
    UserListFilter, UserListResponse, UserWithRolesResponse,
    UserAdminUpdate, MessageResponse, SuccessResponse, RoleResponse
)
from ...core.user_security import (
    revoke_all_user_sessions, unlock_account, get_user_permissions,
    hash_password
)

router = APIRouter(prefix="/admin", tags=["Admin - User Management"])


# ============================================================================
# User Management Endpoints
# ============================================================================

@router.get("/users", response_model=UserListResponse)
async def list_users(
    email: Optional[str] = Query(None, description="Filter by email (partial match)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    created_after: Optional[datetime] = Query(None, description="Filter users created after date"),
    created_before: Optional[datetime] = Query(None, description="Filter users created before date"),
    role_name: Optional[str] = Query(None, description="Filter by role name"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> UserListResponse:
    """
    List all users with filtering and pagination
    
    Returns a paginated list of users with their roles and permissions.
    """
    # Build query
    query = db.query(User)
    
    # Apply filters
    if email:
        query = query.filter(User.email.ilike(f"%{email}%"))
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)
    
    if created_after:
        query = query.filter(User.created_at >= created_after)
    
    if created_before:
        query = query.filter(User.created_at <= created_before)
    
    if role_name:
        query = query.join(UserRole).join(Role).filter(
            Role.name.ilike(f"%{role_name}%"),
            UserRole.is_active == True,
            Role.is_active == True
        )
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    offset = (page - 1) * size
    users = query.offset(offset).limit(size).all()
    
    # Build response
    user_responses = []
    for user in users:
        # Get user roles and convert them properly
        roles_data = []
        for user_role in user.user_roles:
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
        permissions = get_user_permissions(user, db)
        
        user_response = UserWithRolesResponse(
            **user.__dict__,
            roles=roles_data,
            permissions=permissions
        )
        user_responses.append(user_response)
    
    pages = math.ceil(total / size)
    
    return UserListResponse(
        users=user_responses,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/users/{user_id}", response_model=UserWithRolesResponse)
async def get_user_details(
    user_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> UserWithRolesResponse:
    """
    Get detailed user information
    
    Returns detailed information about a specific user including roles and permissions.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Get user roles and convert them properly
    roles_data = []
    for user_role in user.user_roles:
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
    permissions = get_user_permissions(user, db)
    
    return UserWithRolesResponse(
        **user.__dict__,
        roles=roles_data,
        permissions=permissions
    )


@router.put("/users/{user_id}", response_model=UserWithRolesResponse)
async def update_user(
    user_id: str,
    user_update: UserAdminUpdate,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> UserWithRolesResponse:
    """
    Update user information (admin only)
    
    Updates user information including admin-only fields like active status.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update user fields
    update_data = user_update.dict(exclude_unset=True)
    
    for field, value in update_data.items():
        if field == "preferences":
            setattr(user, field, json.dumps(value) if value else None)
        else:
            setattr(user, field, value)
    
    # Update full name if first_name or last_name changed
    if "first_name" in update_data or "last_name" in update_data:
        if user.first_name and user.last_name:
            user.full_name = f"{user.first_name} {user.last_name}"
        elif user.first_name:
            user.full_name = user.first_name
        elif user.last_name:
            user.full_name = user.last_name
        else:
            user.full_name = None
    
    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # Get updated user with roles and convert them properly
    roles_data = []
    for user_role in user.user_roles:
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

    permissions = get_user_permissions(user, db)

    return UserWithRolesResponse(
        **user.__dict__,
        roles=roles_data,
        permissions=permissions
    )


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Delete user account (admin only)
    
    Permanently deletes a user account and all associated data.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Prevent deletion of superusers by non-superusers
    if user.is_superuser and not admin_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete superuser account"
        )
    
    # Prevent self-deletion
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Delete user (cascading will handle related records)
    db.delete(user)
    db.commit()
    
    return MessageResponse(message="User deleted successfully")


@router.post("/users/{user_id}/unlock", response_model=MessageResponse)
async def unlock_user_account(
    user_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Unlock user account (admin only)
    
    Unlocks a user account that has been locked due to failed login attempts.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    success = unlock_account(user.email, db)
    if success:
        return MessageResponse(message="User account unlocked successfully")
    else:
        return MessageResponse(message="User account was not locked")


@router.post("/users/{user_id}/revoke-sessions", response_model=MessageResponse)
async def revoke_user_sessions(
    user_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Revoke all user sessions (admin only)
    
    Revokes all active sessions for a user, forcing them to re-authenticate.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    count = revoke_all_user_sessions(user_id, db=db)
    
    return MessageResponse(
        message=f"Revoked {count} active sessions for user"
    )


@router.post("/users/{user_id}/reset-password", response_model=MessageResponse)
async def admin_reset_password(
    user_id: str,
    new_password: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Reset user password (admin only)
    
    Resets a user's password without requiring the old password.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Update password
    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.utcnow()
    user.updated_at = datetime.utcnow()
    user.failed_login_attempts = 0
    user.locked_until = None
    
    db.commit()
    
    # Revoke all sessions for security
    revoke_all_user_sessions(user_id, db=db)
    
    return MessageResponse(message="Password reset successfully")


# ============================================================================
# Role Management Endpoints
# ============================================================================

@router.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> List[RoleResponse]:
    """
    List all roles
    
    Returns a list of all available roles in the system.
    """
    roles = db.query(Role).filter(Role.is_active == True).all()
    
    role_responses = []
    for role in roles:
        permissions = json.loads(role.permissions or "[]")
        role_responses.append(RoleResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            description=role.description,
            permissions=permissions,
            is_system=role.is_system
        ))
    
    return role_responses


@router.post("/users/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def assign_role_to_user(
    user_id: str,
    role_id: str,
    expires_in_days: Optional[int] = Query(None, description="Role expiration in days"),
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Assign role to user (admin only)
    
    Assigns a role to a user with optional expiration.
    """
    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Verify role exists
    role = db.query(Role).filter(Role.id == role_id, Role.is_active == True).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )
    
    # Check if user already has this role
    existing_user_role = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
        UserRole.is_active == True
    ).first()
    
    if existing_user_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role"
        )
    
    # Calculate expiration
    expires_at = None
    if expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)
    
    # Create user role assignment
    user_role = UserRole(
        user_id=user_id,
        role_id=role_id,
        assigned_by=admin_user.id,
        expires_at=expires_at
    )
    
    db.add(user_role)
    db.commit()
    
    return MessageResponse(
        message=f"Role '{role.display_name}' assigned to user successfully"
    )


@router.delete("/users/{user_id}/roles/{role_id}", response_model=MessageResponse)
async def remove_role_from_user(
    user_id: str,
    role_id: str,
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> MessageResponse:
    """
    Remove role from user (admin only)
    
    Removes a role assignment from a user.
    """
    # Find the user role assignment
    user_role = db.query(UserRole).filter(
        UserRole.user_id == user_id,
        UserRole.role_id == role_id,
        UserRole.is_active == True
    ).first()
    
    if not user_role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User role assignment not found"
        )
    
    # Deactivate the role assignment
    user_role.is_active = False
    db.commit()
    
    return MessageResponse(message="Role removed from user successfully")


# ============================================================================
# Statistics and Analytics Endpoints
# ============================================================================

@router.get("/stats/users", response_model=dict)
async def get_user_statistics(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get user statistics
    
    Returns various statistics about users in the system.
    """
    # Total users
    total_users = db.query(User).count()
    
    # Active users
    active_users = db.query(User).filter(User.is_active == True).count()
    
    # Verified users
    verified_users = db.query(User).filter(User.is_verified == True).count()
    
    # Users created in the last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = db.query(User).filter(User.created_at >= thirty_days_ago).count()
    
    # Users who logged in in the last 30 days
    active_users_30d = db.query(User).filter(
        User.last_login_at >= thirty_days_ago
    ).count()
    
    # Failed login attempts in the last 24 hours
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    failed_logins_24h = db.query(LoginAttempt).filter(
        LoginAttempt.attempted_at >= twenty_four_hours_ago,
        LoginAttempt.success == False
    ).count()
    
    # Active sessions
    active_sessions = db.query(UserSession).filter(
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ).count()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "verified_users": verified_users,
        "new_users_30d": new_users_30d,
        "active_users_30d": active_users_30d,
        "failed_logins_24h": failed_logins_24h,
        "active_sessions": active_sessions,
        "verification_rate": round((verified_users / total_users * 100) if total_users > 0 else 0, 2),
        "activity_rate": round((active_users_30d / total_users * 100) if total_users > 0 else 0, 2)
    }


@router.get("/stats/security", response_model=dict)
async def get_security_statistics(
    admin_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get security-related statistics
    
    Returns statistics about security events and account status.
    """
    # Locked accounts
    locked_accounts = db.query(User).filter(
        User.locked_until.isnot(None),
        User.locked_until > datetime.utcnow()
    ).count()
    
    # Recent login attempts (last 24 hours)
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    recent_attempts = db.query(LoginAttempt).filter(
        LoginAttempt.attempted_at >= twenty_four_hours_ago
    ).count()
    
    successful_logins = db.query(LoginAttempt).filter(
        LoginAttempt.attempted_at >= twenty_four_hours_ago,
        LoginAttempt.success == True
    ).count()
    
    failed_logins = db.query(LoginAttempt).filter(
        LoginAttempt.attempted_at >= twenty_four_hours_ago,
        LoginAttempt.success == False
    ).count()
    
    # Suspicious activity (high failure rate IPs)
    suspicious_ips = db.query(LoginAttempt.ip_address).filter(
        LoginAttempt.attempted_at >= twenty_four_hours_ago,
        LoginAttempt.success == False
    ).group_by(LoginAttempt.ip_address).having(
        func.count(LoginAttempt.id) >= 5
    ).count()
    
    return {
        "locked_accounts": locked_accounts,
        "login_attempts_24h": recent_attempts,
        "successful_logins_24h": successful_logins,
        "failed_logins_24h": failed_logins,
        "suspicious_ips_24h": suspicious_ips,
        "success_rate": round((successful_logins / recent_attempts * 100) if recent_attempts > 0 else 0, 2)
    }
