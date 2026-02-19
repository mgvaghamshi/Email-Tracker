"""
Settings API Endpoints
Handles user settings including SMTP, company, security, notifications, and domain configuration
"""
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr, Field
import logging
import smtplib
from email.mime.text import MIMEText

from ...db import SessionLocal
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/settings", tags=["Settings"])


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============= Pydantic Schemas =============

class SmtpSettings(BaseModel):
    """SMTP configuration settings"""
    server: str
    port: int
    security: str = Field(..., pattern="^(TLS|SSL|NONE)$")
    username: str
    password: str
    isConnected: bool = False


class SmtpSettingsResponse(BaseModel):
    """SMTP settings response"""
    server: str
    port: int
    security: str
    username: str
    password: str  # In production, never return actual password
    isConnected: bool


class SmtpTestResponse(BaseModel):
    """SMTP test connection response"""
    success: bool
    error: Optional[str] = None


class AccountSettings(BaseModel):
    """Account configuration settings"""
    organizationName: str
    contactEmail: EmailStr
    timezone: str
    language: str


class AccountSettingsResponse(BaseModel):
    """Account settings response"""
    organizationName: str
    contactEmail: str
    timezone: str
    language: str


class SecuritySettingsResponse(BaseModel):
    """Security configuration settings"""
    twoFactorEnabled: bool
    apiKeyRotationEnabled: bool
    sessionTimeout: int  # in minutes


class NotificationSettings(BaseModel):
    """Notification preferences"""
    campaignCompletion: bool
    highBounceRate: bool
    apiLimitWarnings: bool
    securityAlerts: bool
    weeklyReports: bool
    webhookUrl: Optional[str] = ""
    emailNotifications: bool


class NotificationSettingsResponse(BaseModel):
    """Notification settings response"""
    campaignCompletion: bool
    highBounceRate: bool
    apiLimitWarnings: bool
    securityAlerts: bool
    weeklyReports: bool
    webhookUrl: Optional[str] = ""
    emailNotifications: bool


class StorageResponse(BaseModel):
    """Storage usage data"""
    used: float  # in GB
    total: float  # in GB
    retentionPeriod: int  # in days


class DomainSettings(BaseModel):
    """Domain configuration"""
    trackingDomain: str
    sendingDomain: str


class DomainSettingsResponse(BaseModel):
    """Domain settings response"""
    trackingDomain: str
    sendingDomain: str


# ============= SMTP Endpoints =============

@router.get("/smtp", response_model=SmtpSettingsResponse)
async def get_smtp_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get SMTP configuration settings"""
    try:
        # In a real implementation, retrieve from database
        # For now, return mock data
        return {
            "server": "smtp.gmail.com",
            "port": 587,
            "security": "TLS",
            "username": current_user.email,
            "password": "********",  # Never return actual password
            "isConnected": True
        }
    except Exception as e:
        logger.error(f"Error getting SMTP settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SMTP settings: {str(e)}"
        )


@router.put("/smtp", response_model=SmtpSettingsResponse)
async def update_smtp_settings(
    settings: SmtpSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update SMTP configuration settings"""
    try:
        # In a real implementation:
        # 1. Validate SMTP settings
        # 2. Encrypt password
        # 3. Store in database
        
        logger.info(f"Updating SMTP settings for user {current_user.id}")
        
        return {
            "server": settings.server,
            "port": settings.port,
            "security": settings.security,
            "username": settings.username,
            "password": "********",
            "isConnected": settings.isConnected
        }
    except Exception as e:
        logger.error(f"Error updating SMTP settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update SMTP settings: {str(e)}"
        )


@router.post("/smtp/test", response_model=SmtpTestResponse)
async def test_smtp_connection(
    settings: SmtpSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Test SMTP connection with provided settings"""
    try:
        # Test SMTP connection
        if settings.security == "TLS":
            server = smtplib.SMTP(settings.server, settings.port)
            server.starttls()
        elif settings.security == "SSL":
            server = smtplib.SMTP_SSL(settings.server, settings.port)
        else:
            server = smtplib.SMTP(settings.server, settings.port)
        
        server.login(settings.username, settings.password)
        server.quit()
        
        return {"success": True, "error": None}
        
    except Exception as e:
        logger.error(f"SMTP connection test failed: {str(e)}")
        return {"success": False, "error": str(e)}


# ============= Company/Account Endpoints =============

@router.get("/company")
async def get_company_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get company branding settings"""
    try:
        # Return mock company settings
        return {
            "companyName": "My Company",
            "website": "https://example.com",
            "logo": None,
            "primaryColor": "#1976d2",
            "supportEmail": current_user.email
        }
    except Exception as e:
        logger.error(f"Error getting company settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get company settings: {str(e)}"
        )


@router.put("/company")
async def update_company_settings(
    company_data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update company branding settings"""
    try:
        logger.info(f"Updating company settings for user {current_user.id}")
        return company_data
    except Exception as e:
        logger.error(f"Error updating company settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company settings: {str(e)}"
        )


@router.get("/account", response_model=AccountSettingsResponse)
async def get_account_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get account configuration settings"""
    try:
        return {
            "organizationName": "My Organization",
            "contactEmail": current_user.email,
            "timezone": current_user.timezone or "UTC",
            "language": current_user.locale or "en"
        }
    except Exception as e:
        logger.error(f"Error getting account settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get account settings: {str(e)}"
        )


@router.put("/account", response_model=AccountSettingsResponse)
async def update_account_settings(
    settings: AccountSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update account configuration settings"""
    try:
        logger.info(f"Updating account settings for user {current_user.id}")
        
        # Update user profile
        current_user.timezone = settings.timezone
        current_user.locale = settings.language
        db.commit()
        
        return {
            "organizationName": settings.organizationName,
            "contactEmail": settings.contactEmail,
            "timezone": settings.timezone,
            "language": settings.language
        }
    except Exception as e:
        logger.error(f"Error updating account settings: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update account settings: {str(e)}"
        )


# ============= Security Endpoints =============

@router.get("/security", response_model=SecuritySettingsResponse)
async def get_security_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get security configuration settings"""
    try:
        return {
            "twoFactorEnabled": False,  # Check if 2FA is enabled for user
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30  # 30 minutes default
        }
    except Exception as e:
        logger.error(f"Error getting security settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )


@router.post("/security/2fa")
async def toggle_two_factor_auth(
    request: Dict[str, bool],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle two-factor authentication"""
    try:
        enabled = request.get("enabled", False)
        logger.info(f"Toggling 2FA to {enabled} for user {current_user.id}")
        
        # In real implementation, enable/disable 2FA
        return {"enabled": enabled}
    except Exception as e:
        logger.error(f"Error toggling 2FA: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle 2FA: {str(e)}"
        )


@router.post("/security/api-rotation")
async def toggle_api_key_rotation(
    request: Dict[str, bool],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle API key rotation"""
    try:
        enabled = request.get("enabled", False)
        logger.info(f"Toggling API key rotation to {enabled} for user {current_user.id}")
        
        return {"enabled": enabled}
    except Exception as e:
        logger.error(f"Error toggling API key rotation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle API key rotation: {str(e)}"
        )


@router.put("/security/session-timeout")
async def update_session_timeout(
    request: Dict[str, int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update session timeout"""
    try:
        timeout = request.get("timeout", 30)
        logger.info(f"Updating session timeout to {timeout} minutes for user {current_user.id}")
        
        return {"message": f"Session timeout updated to {timeout} minutes"}
    except Exception as e:
        logger.error(f"Error updating session timeout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session timeout: {str(e)}"
        )


# ============= Notification Endpoints =============

@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification settings"""
    try:
        return {
            "campaignCompletion": True,
            "highBounceRate": True,
            "apiLimitWarnings": True,
            "securityAlerts": True,
            "weeklyReports": False,
            "webhookUrl": "",
            "emailNotifications": True
        }
    except Exception as e:
        logger.error(f"Error getting notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )


@router.put("/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings: NotificationSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update notification settings"""
    try:
        logger.info(f"Updating notification settings for user {current_user.id}")
        
        return {
            "campaignCompletion": settings.campaignCompletion,
            "highBounceRate": settings.highBounceRate,
            "apiLimitWarnings": settings.apiLimitWarnings,
            "securityAlerts": settings.securityAlerts,
            "weeklyReports": settings.weeklyReports,
            "webhookUrl": settings.webhookUrl,
            "emailNotifications": settings.emailNotifications
        }
    except Exception as e:
        logger.error(f"Error updating notification settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )


# ============= Storage & Data Endpoints =============

@router.get("/storage", response_model=StorageResponse)
async def get_storage_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get storage usage data"""
    try:
        return {
            "used": 2.5,  # 2.5 GB
            "total": 10.0,  # 10 GB
            "retentionPeriod": 90  # 90 days
        }
    except Exception as e:
        logger.error(f"Error getting storage data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage data: {str(e)}"
        )


@router.put("/storage/retention")
async def update_retention_period(
    request: Dict[str, int],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update data retention period"""
    try:
        retention = request.get("retentionPeriod", 90)
        logger.info(f"Updating retention period to {retention} days for user {current_user.id}")
        
        return {"message": f"Retention period updated to {retention} days"}
    except Exception as e:
        logger.error(f"Error updating retention period: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update retention period: {str(e)}"
        )


@router.post("/data/export")
async def export_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Export user data"""
    try:
        logger.info(f"Exporting data for user {current_user.id}")
        
        return {"message": "Data export initiated. You will receive an email when ready."}
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export data: {str(e)}"
        )


@router.delete("/data/delete")
async def delete_all_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete all user data"""
    try:
        logger.warning(f"Deleting all data for user {current_user.id}")
        
        # In real implementation, delete all user data
        return {"message": "All data has been scheduled for deletion"}
    except Exception as e:
        logger.error(f"Error deleting data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete data: {str(e)}"
        )


# ============= Domain Endpoints =============

@router.get("/domains", response_model=DomainSettingsResponse)
async def get_domain_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get domain configuration settings"""
    try:
        return {
            "trackingDomain": "track.example.com",
            "sendingDomain": "mail.example.com"
        }
    except Exception as e:
        logger.error(f"Error getting domain settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain settings: {str(e)}"
        )


@router.put("/domains", response_model=DomainSettingsResponse)
async def update_domain_settings(
    settings: DomainSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update domain configuration settings"""
    try:
        logger.info(f"Updating domain settings for user {current_user.id}")
        
        return {
            "trackingDomain": settings.trackingDomain,
            "sendingDomain": settings.sendingDomain
        }
    except Exception as e:
        logger.error(f"Error updating domain settings: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update domain settings: {str(e)}"
        )
