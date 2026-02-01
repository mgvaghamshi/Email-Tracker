"""
Two-Factor Authentication API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Any
import io
import base64
from datetime import datetime, timedelta

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.user_models import User
from ...database.two_factor_models import TwoFactorAuth, TwoFactorAttempt, TwoFactorSession
from ...schemas.two_factor import (
    TwoFactorSetupRequest, TwoFactorSetupResponse,
    TwoFactorVerifyRequest, TwoFactorVerifyResponse,
    TwoFactorLoginRequest, TwoFactorLoginResponse,
    TwoFactorDisableRequest, TwoFactorStatusResponse,
    TwoFactorBackupCodesResponse, TwoFactorRecoveryRequest, TwoFactorRecoveryResponse,
    TwoFactorSessionResponse
)
from ...core.user_security import verify_password

router = APIRouter(prefix="/auth/2fa", tags=["Two-Factor Authentication"])


@router.get("/status", response_model=TwoFactorStatusResponse)
async def get_2fa_status(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> TwoFactorStatusResponse:
    """Get current 2FA status for the user"""
    try:
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if not two_factor:
            return TwoFactorStatusResponse(
                is_enabled=False,
                is_verified=False,
                backup_codes_remaining=0,
                setup_completed_at=None,
                last_used_at=None
            )
        
        return TwoFactorStatusResponse(
            is_enabled=two_factor.is_enabled,
            is_verified=two_factor.is_verified,
            backup_codes_remaining=two_factor.get_backup_codes_remaining(),
            setup_completed_at=two_factor.setup_completed_at,
            last_used_at=two_factor.last_used_at
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get 2FA status: {str(e)}"
        )


@router.post("/setup", response_model=TwoFactorSetupResponse)
async def setup_2fa(
    request: TwoFactorSetupRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> TwoFactorSetupResponse:
    """Initialize 2FA setup for the user"""
    try:
        # Check if user already has 2FA enabled
        existing_2fa = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if existing_2fa and existing_2fa.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is already enabled"
            )
        
        # Create or update 2FA record
        if existing_2fa:
            two_factor = existing_2fa
            two_factor.secret = TwoFactorAuth.generate_secret()
            two_factor.is_enabled = False
            two_factor.is_verified = False
        else:
            two_factor = TwoFactorAuth(
                user_id=current_user.id,
                secret=TwoFactorAuth.generate_secret()
            )
            db.add(two_factor)
        
        # Generate backup codes
        backup_codes = two_factor.generate_backup_codes()
        
        # Get provisioning URI
        setup_uri = two_factor.get_provisioning_uri(current_user.email)
        
        db.commit()
        
        return TwoFactorSetupResponse(
            secret=two_factor.secret,
            qr_code_url=f"/api/v1/auth/2fa/qr?user_id={current_user.id}",
            backup_codes=backup_codes,
            setup_uri=setup_uri
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to setup 2FA: {str(e)}"
        )


@router.get("/qr")
async def get_qr_code(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> StreamingResponse:
    """Get QR code image for 2FA setup"""
    try:
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if not two_factor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA setup not found"
            )
        
        # Generate QR code
        qr_image_bytes = two_factor.generate_qr_code(current_user.email)
        
        # Update database
        db.commit()
        
        # Return image as stream
        return StreamingResponse(
            io.BytesIO(qr_image_bytes),
            media_type="image/png",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {str(e)}"
        )


@router.post("/verify", response_model=TwoFactorVerifyResponse)
async def verify_2fa_setup(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> TwoFactorVerifyResponse:
    """Verify 2FA setup with TOTP code"""
    try:
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if not two_factor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="2FA setup not found"
            )
        
        if two_factor.is_enabled and two_factor.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="2FA is already verified and enabled"
            )
        
        # Verify the code
        if two_factor.verify_code(request.code, allow_reuse=True):  # Allow reuse during setup
            two_factor.is_enabled = True
            two_factor.is_verified = True
            two_factor.setup_completed_at = datetime.utcnow()
            
            # Log successful attempt
            attempt = TwoFactorAttempt(
                two_factor_auth_id=two_factor.id,
                code_type="totp",
                success=True,
                ip_address=None,  # TODO: Extract from request
                user_agent=None   # TODO: Extract from request
            )
            db.add(attempt)
            
            db.commit()
            
            return TwoFactorVerifyResponse(
                success=True,
                message="Two-factor authentication enabled successfully",
                backup_codes_remaining=two_factor.get_backup_codes_remaining()
            )
        else:
            # Log failed attempt
            attempt = TwoFactorAttempt(
                two_factor_auth_id=two_factor.id,
                code_type="totp",
                success=False,
                failure_reason="invalid_code",
                ip_address=None,  # TODO: Extract from request
                user_agent=None   # TODO: Extract from request
            )
            db.add(attempt)
            db.commit()
            
            return TwoFactorVerifyResponse(
                success=False,
                message="Invalid verification code. Please try again."
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify 2FA: {str(e)}"
        )


@router.post("/login", response_model=TwoFactorLoginResponse)
async def verify_2fa_login(
    request: TwoFactorLoginRequest,
    db: Session = Depends(get_db)
) -> TwoFactorLoginResponse:
    """Verify 2FA code during login process"""
    try:
        # Find and validate session
        session = db.query(TwoFactorSession).filter(
            TwoFactorSession.session_token == request.session_token,
            TwoFactorSession.purpose == "login"
        ).first()
        
        if not session or not session.is_valid():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired session token"
            )
        
        # Get user and 2FA
        user = db.query(User).filter(User.id == session.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == user.id
        ).first()
        
        if not two_factor or not two_factor.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled"
            )
        
        # Verify code (TOTP or backup code)
        verification_success = False
        code_type = "totp"
        backup_codes_remaining = two_factor.get_backup_codes_remaining()
        
        if len(request.code) == 6:
            # Try TOTP code
            verification_success = two_factor.verify_code(request.code)
        elif len(request.code) == 8:
            # Try backup code
            verification_success = two_factor.verify_backup_code(request.code)
            code_type = "backup"
            backup_codes_remaining = two_factor.get_backup_codes_remaining()
        
        # Log attempt
        attempt = TwoFactorAttempt(
            two_factor_auth_id=two_factor.id,
            code_type=code_type,
            success=verification_success,
            failure_reason=None if verification_success else "invalid_code",
            ip_address=session.ip_address,
            user_agent=session.user_agent
        )
        db.add(attempt)
        
        if verification_success:
            # Mark session as verified and consumed
            session.mark_verified()
            session.consume()
            
            # Generate JWT tokens
            from ...core.user_security import JWTManager
            jwt_manager = JWTManager()
            
            access_token, refresh_token, session_id = jwt_manager.create_token_pair(
                user=user,
                device_info=None,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                db=db
            )
            
            db.commit()
            
            return TwoFactorLoginResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=3600,  # 1 hour
                backup_codes_remaining=backup_codes_remaining
            )
        else:
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 2FA code"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify 2FA login: {str(e)}"
        )


@router.post("/disable", response_model=TwoFactorVerifyResponse)
async def disable_2fa(
    request: TwoFactorDisableRequest,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> TwoFactorVerifyResponse:
    """Disable 2FA for the user"""
    try:
        # Verify password
        if not verify_password(request.password, current_user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid password"
            )
        
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if not two_factor or not two_factor.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled"
            )
        
        # If code provided, verify it
        if request.code:
            verification_success = False
            if len(request.code) == 6:
                verification_success = two_factor.verify_code(request.code)
            elif len(request.code) == 8:
                verification_success = two_factor.verify_backup_code(request.code)
            
            if not verification_success:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid 2FA code"
                )
        
        # Disable 2FA
        two_factor.reset_2fa()
        db.commit()
        
        return TwoFactorVerifyResponse(
            success=True,
            message="Two-factor authentication disabled successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable 2FA: {str(e)}"
        )


@router.post("/backup-codes", response_model=TwoFactorBackupCodesResponse)
async def regenerate_backup_codes(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
) -> TwoFactorBackupCodesResponse:
    """Generate new backup codes for 2FA"""
    try:
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == current_user.id
        ).first()
        
        if not two_factor or not two_factor.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Two-factor authentication is not enabled"
            )
        
        # Generate new backup codes
        backup_codes = two_factor.generate_backup_codes()
        db.commit()
        
        return TwoFactorBackupCodesResponse(
            backup_codes=backup_codes,
            message="New backup codes generated successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate backup codes: {str(e)}"
        )


@router.post("/recovery", response_model=TwoFactorRecoveryResponse)
async def request_2fa_recovery(
    request: TwoFactorRecoveryRequest,
    db: Session = Depends(get_db)
) -> TwoFactorRecoveryResponse:
    """Request 2FA account recovery"""
    try:
        # Find user by email
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            # Don't reveal if email exists or not
            return TwoFactorRecoveryResponse(
                message="If the email address is associated with an account, recovery instructions have been sent"
            )
        
        two_factor = db.query(TwoFactorAuth).filter(
            TwoFactorAuth.user_id == user.id
        ).first()
        
        if not two_factor or not two_factor.is_enabled:
            return TwoFactorRecoveryResponse(
                message="If the email address is associated with an account, recovery instructions have been sent"
            )
        
        # TODO: Send recovery email with special recovery token
        # This would typically involve generating a special recovery token
        # and sending an email with instructions to disable 2FA
        
        return TwoFactorRecoveryResponse(
            message="Recovery instructions have been sent to your email address"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process recovery request: {str(e)}"
        )


@router.post("/session", response_model=TwoFactorSessionResponse)
async def create_2fa_session(
    user_id: str,
    purpose: str = "login",
    ip_address: str = None,
    user_agent: str = None,
    db: Session = Depends(get_db)
) -> TwoFactorSessionResponse:
    """Create a temporary 2FA session (internal use)"""
    try:
        # Create session
        session_token = TwoFactorSession.generate_session_token()
        session = TwoFactorSession(
            user_id=user_id,
            session_token=session_token,
            purpose=purpose,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.utcnow() + timedelta(minutes=5)  # 5 minute expiry
        )
        
        db.add(session)
        db.commit()
        
        return TwoFactorSessionResponse(
            session_token=session_token,
            expires_in=300,  # 5 minutes
            requires_2fa=True
        )
    
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create 2FA session: {str(e)}"
        )
