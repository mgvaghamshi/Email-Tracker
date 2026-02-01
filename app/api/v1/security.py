"""
Enhanced Security Management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import bcrypt
import secrets
import ipaddress

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.user_models import User, UserSession, LoginAttempt
from ...database.security_models import (
    SecurityAuditLog, PasswordResetToken, SecuritySettings
)
from ...database.two_factor_models import TwoFactorAuth
from ...schemas.security import (
    PasswordChangeRequest, PasswordChangeResponse,
    SecuritySettingsResponse, SecuritySettingsUpdateRequest,
    SessionResponse, AuditLogResponse, 
    SecurityStatsResponse, PasswordStrengthResponse, PasswordStrengthRequest
)
from ...core.user_security import (
    hash_password, verify_password, get_current_session_id_from_token, 
    update_session_activity, revoke_session, revoke_all_user_sessions
)
from ...core.device_detection import get_device_display_name
from ...core.time_formatter import format_timestamp_with_relative, get_relative_time
# from ...core.email import send_security_notification_email  # TODO: Implement

router = APIRouter(prefix="/security", tags=["Security Management"])


# ============================================================================
# Password Management
# ============================================================================

@router.post("/password/change", response_model=PasswordChangeResponse)
async def change_password(
    request: PasswordChangeRequest,
    background_tasks: BackgroundTasks,
    req: Request,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> PasswordChangeResponse:
    """Change user password with enhanced security"""
    try:
        # Verify current password
        if not verify_password(request.current_password, current_user.password_hash):
            # Log failed attempt
            await log_security_event(
                db, current_user.id, "password_change_failed",
                "Failed password change attempt - invalid current password",
                False, req
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate password strength
        strength_result = check_password_strength(request.new_password)
        if not strength_result['is_strong']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Password is too weak: {', '.join(strength_result['issues'])}"
            )
        
        # Hash new password
        new_password_hash = hash_password(request.new_password)
        
        # Get the user in the current session to avoid session persistence issues
        db_user = db.query(User).filter(User.id == current_user.id).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Update password
        db_user.password_hash = new_password_hash
        db_user.password_changed_at = datetime.utcnow()
        db_user.failed_login_attempts = 0  # Reset failed attempts
        
        # Also update SecuritySettings last_password_change for consistency
        settings = SecuritySettings.get_or_create_for_user(db, current_user.id)
        settings.last_password_change = db_user.password_changed_at
        settings.updated_at = datetime.utcnow()
        
        # Log successful password change
        await log_security_event(
            db, current_user.id, "password_changed",
            "Password changed successfully", True, req
        )
        
        # Commit changes
        db.commit()
        
        # Refresh the user object to ensure it's up to date
        db.refresh(db_user)
        
        # Send security notification email
        # TODO: Implement email notifications
        # background_tasks.add_task(
        #     send_security_notification_email,
        #     current_user.email,
        #     "Password Changed",
        #     f"Your password was changed at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        #     get_client_ip(req)
        # )
        
        return PasswordChangeResponse(
            success=True,
            message="Password changed successfully",
            password_strength=strength_result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        await log_security_event(
            db, current_user.id, "password_change_error",
            f"Password change error: {str(e)}", False, req
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change password"
        )


@router.post("/password/strength")
async def check_password_strength_endpoint(
    request: PasswordStrengthRequest,
    current_user: User = Depends(get_current_user_from_jwt)
) -> PasswordStrengthResponse:
    """Check password strength"""
    result = check_password_strength(request.password)
    return PasswordStrengthResponse(**result)


# ============================================================================
# Security Settings Management
# ============================================================================

@router.get("/settings", response_model=SecuritySettingsResponse)
async def get_security_settings(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> SecuritySettingsResponse:
    """Get user security settings and status"""
    try:
        # Get security settings
        settings = SecuritySettings.get_or_create_for_user(db, current_user.id)
        
        # Get 2FA status
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        # Get active sessions count
        active_sessions = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).count()
        
        # Get recent login attempts
        recent_attempts = db.query(LoginAttempt).filter(
            LoginAttempt.user_id == current_user.id,
            LoginAttempt.attempted_at >= datetime.utcnow() - timedelta(days=7)
        ).count()
        
        # Calculate password age
        password_age_days = None
        if current_user.password_changed_at:
            password_age_days = (datetime.utcnow() - current_user.password_changed_at).days
        
        return SecuritySettingsResponse(
            two_factor_enabled=two_factor.is_enabled if two_factor else False,
            two_factor_verified=two_factor.is_verified if two_factor else False,
            backup_codes_remaining=two_factor.get_backup_codes_remaining() if two_factor else 0,
            password_changed_at=current_user.password_changed_at,
            password_age_days=password_age_days,
            active_sessions_count=active_sessions,
            recent_login_attempts=recent_attempts,
            session_timeout_hours=settings.session_timeout_hours,
            max_concurrent_sessions=settings.max_concurrent_sessions,
            login_notifications=settings.login_notifications,
            suspicious_activity_alerts=settings.suspicious_activity_alerts,
            api_key_rotation_enabled=settings.api_key_rotation_enabled,
            api_key_rotation_days=settings.api_key_rotation_days,
            require_password_change=settings.require_password_change,
            password_change_days=settings.password_change_days
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )


@router.put("/settings", response_model=SecuritySettingsResponse)
async def update_security_settings(
    request: SecuritySettingsUpdateRequest,
    req: Request,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> SecuritySettingsResponse:
    """Update user security settings"""
    try:
        settings = SecuritySettings.get_or_create_for_user(db, current_user.id)
        
        # Update settings
        if request.session_timeout_hours is not None:
            settings.session_timeout_hours = request.session_timeout_hours
        if request.max_concurrent_sessions is not None:
            settings.max_concurrent_sessions = request.max_concurrent_sessions
        if request.login_notifications is not None:
            settings.login_notifications = request.login_notifications
        if request.suspicious_activity_alerts is not None:
            settings.suspicious_activity_alerts = request.suspicious_activity_alerts
        if request.api_key_rotation_enabled is not None:
            settings.api_key_rotation_enabled = request.api_key_rotation_enabled
        if request.api_key_rotation_days is not None:
            settings.api_key_rotation_days = request.api_key_rotation_days
        if request.require_password_change is not None:
            settings.require_password_change = request.require_password_change
        if request.password_change_days is not None:
            settings.password_change_days = request.password_change_days
        
        settings.updated_at = datetime.utcnow()
        
        # Log settings change
        await log_security_event(
            db, current_user.id, "security_settings_updated",
            "Security settings updated", True, req
        )
        
        db.commit()
        
        # Return updated settings
        return await get_security_settings(current_user, db)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update security settings: {str(e)}"
        )


# ============================================================================
# Session Management
# ============================================================================

@router.get("/sessions", response_model=List[SessionResponse])
async def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> List[SessionResponse]:
    """Get all active user sessions"""
    try:
        # Get current session ID from the JWT token
        auth_header = request.headers.get("authorization", "")
        current_session_id = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            current_session_id = get_current_session_id_from_token(token)
        
        sessions = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True,
            UserSession.expires_at > datetime.utcnow()
        ).order_by(desc(UserSession.last_activity)).all()
        
        result = []
        for session in sessions:
            # Parse device info if available
            device_name = "Unknown Device"
            if session.device_info:
                try:
                    import json
                    device_data = json.loads(session.device_info)
                    device_name = device_data.get("device_display_name") or get_device_display_name(device_data)
                except Exception:
                    pass
            
            # If device name is still generic, try to parse user agent
            if device_name == "Unknown Device" and session.user_agent:
                try:
                    from ...core.device_detection import parse_device_info
                    device_data = parse_device_info(session.user_agent)
                    device_name = get_device_display_name(device_data)
                except Exception:
                    pass
            
            result.append(SessionResponse(
                id=session.id,
                device_name=device_name,
                ip_address=session.ip_address or "Unknown",
                user_agent=session.user_agent,
                location=session.location,
                created_at=session.created_at,
                last_activity=session.last_activity,
                last_activity_relative=get_relative_time(session.last_activity),
                expires_at=session.expires_at,
                is_current=session.id == current_session_id
            ))
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sessions: {str(e)}"
        )


@router.delete("/sessions/all")
async def revoke_all_sessions_endpoint(
    req: Request,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Revoke all user sessions except current"""
    try:
        # Get current session ID to exclude it
        auth_header = req.headers.get("authorization", "")
        current_session_id = None
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            current_session_id = get_current_session_id_from_token(token)
        
        # Count sessions before revoking
        sessions_query = db.query(UserSession).filter(
            UserSession.user_id == current_user.id,
            UserSession.is_active == True
        )
        
        if current_session_id:
            sessions_query = sessions_query.filter(UserSession.id != current_session_id)
        
        sessions_count = sessions_query.count()
        
        # Use the improved revoke_all_user_sessions function
        revoked_count = revoke_all_user_sessions(
            user_id=current_user.id, 
            except_session_id=current_session_id,
            db=db
        )
        
        # Log mass session revocation
        await log_security_event(
            db, current_user.id, "all_sessions_revoked",
            f"All {revoked_count} sessions revoked by user", True, req
        )
        
        return {
            "message": "All sessions revoked successfully",
            "revoked_count": revoked_count
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke sessions: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def revoke_session_endpoint(
    session_id: str,
    req: Request,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Revoke a specific session"""
    try:
        session = db.query(UserSession).filter(
            UserSession.id == session_id,
            UserSession.user_id == current_user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Use the improved revoke_session function
        success = revoke_session(session_id, reason="manual_revocation", db=db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to revoke session"
            )
        
        # Log session revocation
        await log_security_event(
            db, current_user.id, "session_revoked",
            f"Session {session_id} revoked manually", True, req,
            security_metadata={'session_id': session_id, 'revoked_ip': session.ip_address}
        )
        
        return {"message": "Session revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke session: {str(e)}"
        )


# ============================================================================
# Security Audit Log
# ============================================================================

@router.get("/audit", response_model=List[AuditLogResponse])
async def get_audit_log(
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> List[AuditLogResponse]:
    """Get security audit log for the current user"""
    try:
        query = db.query(SecurityAuditLog).filter(
            SecurityAuditLog.user_id == current_user.id
        )
        
        if action:
            query = query.filter(SecurityAuditLog.action == action)
        
        if success is not None:
            query = query.filter(SecurityAuditLog.success == success)
        
        audit_logs = query.order_by(
            desc(SecurityAuditLog.created_at)
        ).offset(skip).limit(limit).all()
        
        return [
            AuditLogResponse(
                id=log.id,
                action=log.action,
                resource_type=log.resource_type,
                resource_id=log.resource_id,
                description=log.description,
                ip_address=log.ip_address,
                user_agent=log.user_agent,
                success=log.success,
                failure_reason=log.failure_reason,
                security_metadata=log.security_metadata,
                timestamp=log.created_at,
                timestamp_relative=get_relative_time(log.created_at)
            )
            for log in audit_logs
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit log: {str(e)}"
        )


@router.get("/audit-log", response_model=List[AuditLogResponse])
async def get_audit_log_alias(
    skip: int = 0,
    limit: int = 50,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> List[AuditLogResponse]:
    """Get security audit log for the current user (alias for /audit)"""
    return await get_audit_log(skip, limit, action, success, current_user, db)


@router.get("/stats", response_model=SecurityStatsResponse)
async def get_security_stats(
    days: int = 30,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> SecurityStatsResponse:
    """Get security statistics for the user"""
    try:
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Login attempts
        total_login_attempts = db.query(LoginAttempt).filter(
            LoginAttempt.user_id == current_user.id,
            LoginAttempt.attempted_at >= start_date
        ).count()
        
        successful_logins = db.query(LoginAttempt).filter(
            LoginAttempt.user_id == current_user.id,
            LoginAttempt.attempted_at >= start_date,
            LoginAttempt.success == True
        ).count()
        
        failed_logins = total_login_attempts - successful_logins
        
        # Unique IP addresses
        unique_ips = db.query(LoginAttempt.ip_address).filter(
            LoginAttempt.user_id == current_user.id,
            LoginAttempt.attempted_at >= start_date,
            LoginAttempt.ip_address.isnot(None)
        ).distinct().count()
        
        # Security events
        security_events = db.query(SecurityAuditLog).filter(
            SecurityAuditLog.user_id == current_user.id,
            SecurityAuditLog.created_at >= start_date
        ).count()
        
        # 2FA usage
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        return SecurityStatsResponse(
            total_login_attempts=total_login_attempts,
            successful_logins=successful_logins,
            failed_logins=failed_logins,
            unique_ip_addresses=unique_ips,
            security_events=security_events,
            two_factor_enabled=two_factor.is_enabled if two_factor else False,
            two_factor_last_used=two_factor.last_used_at if two_factor else None,
            period_days=days
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security stats: {str(e)}"
        )


# ============================================================================
# Helper Functions
# ============================================================================

async def log_security_event(
    db: Session,
    user_id: str,
    action: str,
    description: str,
    success: bool,
    request: Request,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    failure_reason: Optional[str] = None,
    security_metadata: Optional[Dict[str, Any]] = None
):
    """Log a security event"""
    try:
        audit_log = SecurityAuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("User-Agent"),
            success=success,
            failure_reason=failure_reason,
            security_metadata=security_metadata
        )
        db.add(audit_log)
        db.commit()
    except Exception as e:
        # Don't let audit logging break the main operation
        logger.error(f"Failed to log security event: {e}")


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP from request"""
    # Check for forwarded headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to client host
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return None


def parse_user_agent(user_agent: Optional[str]) -> str:
    """Parse user agent to get device/browser name"""
    if not user_agent:
        return "Unknown Device"
    
    user_agent = user_agent.lower()
    
    # Mobile detection
    if any(mobile in user_agent for mobile in ['mobile', 'android', 'iphone', 'ipad']):
        if 'android' in user_agent:
            return "Android Device"
        elif any(ios in user_agent for ios in ['iphone', 'ipad']):
            return "iOS Device"
        else:
            return "Mobile Device"
    
    # Desktop browsers
    if 'chrome' in user_agent:
        return "Chrome Browser"
    elif 'firefox' in user_agent:
        return "Firefox Browser"
    elif 'safari' in user_agent and 'chrome' not in user_agent:
        return "Safari Browser"
    elif 'edge' in user_agent:
        return "Edge Browser"
    
    return "Desktop Browser"


def check_password_strength(password: str) -> Dict[str, Any]:
    """Check password strength and return detailed analysis"""
    issues = []
    score = 0
    
    # Length check
    if len(password) < 8:
        issues.append("Must be at least 8 characters long")
    else:
        score += 1
        if len(password) >= 12:
            score += 1
    
    # Character variety checks
    if not any(c.islower() for c in password):
        issues.append("Must contain lowercase letters")
    else:
        score += 1
    
    if not any(c.isupper() for c in password):
        issues.append("Must contain uppercase letters")
    else:
        score += 1
    
    if not any(c.isdigit() for c in password):
        issues.append("Must contain numbers")
    else:
        score += 1
    
    if not any(c in "!@#$%^&*(),.?\":{}|<>" for c in password):
        issues.append("Must contain special characters")
    else:
        score += 1
    
    # Common patterns check
    common_patterns = ['123456', 'password', 'qwerty', 'abc123']
    if any(pattern in password.lower() for pattern in common_patterns):
        issues.append("Avoid common patterns")
        score -= 1
    
    # Determine strength
    if score >= 5:
        strength = "Strong"
    elif score >= 3:
        strength = "Medium"
    else:
        strength = "Weak"
    
    return {
        'is_strong': len(issues) == 0 and score >= 4,
        'strength': strength,
        'score': max(0, score),
        'max_score': 6,
        'issues': issues
    }
