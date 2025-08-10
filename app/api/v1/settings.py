"""
Settings and configuration management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import smtplib

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...config import settings as app_settings
from ...database.user_models import ApiKey, User
from ...schemas.settings import (
    SmtpSettings, SmtpSettingsResponse, SmtpTestResponse,
    AccountSettings, AccountSettingsResponse,
    SecuritySettings, SecuritySettingsResponse,
    NotificationSettings, NotificationSettingsResponse,
    StorageData, StorageResponse,
    DomainSettings, DomainSettingsResponse, DomainStatusResponse
)
from datetime import datetime, timedelta

router = APIRouter(prefix="/settings", tags=["Settings"])

# In-memory storage for settings (in production, use database)
_settings_store = {}

def get_settings_key(setting_type: str, api_key_id: str = "default") -> str:
    """Generate a unique key for settings storage"""
    return f"{setting_type}:{api_key_id}"

def load_setting(setting_type: str, default_value: Any, api_key_id: str = "default") -> Any:
    """Load a setting from storage with fallback to default"""
    key = get_settings_key(setting_type, api_key_id)
    return _settings_store.get(key, default_value)

def save_setting(setting_type: str, value: Any, api_key_id: str = "default"):
    """Save a setting to storage"""
    key = get_settings_key(setting_type, api_key_id)
    _settings_store[key] = value

@router.get("/smtp", response_model=SmtpSettingsResponse)
async def get_smtp_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> SmtpSettingsResponse:
    """Get SMTP configuration settings"""
    try:
        # Load from storage or use app defaults
        default_settings = {
            "server": app_settings.smtp_server,
            "port": app_settings.smtp_port,
            "security": "TLS" if app_settings.smtp_use_tls else ("SSL" if app_settings.smtp_use_ssl else "NONE"),
            "username": app_settings.smtp_username,
            "password": "••••••••" if app_settings.smtp_password else "",
            "isConnected": False
        }
        
        stored_settings = load_setting("smtp", default_settings, current_user.id)
        
        return SmtpSettingsResponse(**stored_settings)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get SMTP settings: {str(e)}"
        )

@router.put("/smtp", response_model=SmtpSettingsResponse)
async def update_smtp_settings(
    settings_data: SmtpSettings,
    current_user: User = Depends(get_current_user_from_jwt)
) -> SmtpSettingsResponse:
    """Update SMTP configuration settings"""
    try:
        # Convert to dict and save
        settings_dict = settings_data.dict()
        save_setting("smtp", settings_dict, current_user.id)
        
        return SmtpSettingsResponse(**settings_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update SMTP settings: {str(e)}"
        )

@router.get("/company")
async def get_company_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, Any]:
    """Get company branding settings"""
    try:
        default_company = {
            "company_name": "Your Company",
            "company_website": "https://yourcompany.com",
            "company_logo": "",
            "company_address": "123 Business St, City, State 12345",
            "support_email": "support@yourcompany.com",
            "privacy_policy_url": "https://yourcompany.com/privacy",
            "terms_of_service_url": "https://yourcompany.com/terms"
        }
        
        stored_company = load_setting("company", default_company, current_user.id)
        return stored_company
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get company settings: {str(e)}"
        )

@router.put("/company")
async def update_company_settings(
    company_data: Dict[str, Any],
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, Any]:
    """Update company branding settings"""
    try:
        # Validate required fields
        required_fields = ["company_name"]
        for field in required_fields:
            if field not in company_data or not company_data[field]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required field: {field}"
                )
        
        # Save company settings
        save_setting("company", company_data, current_user.id)
        
        return company_data
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update company settings: {str(e)}"
        )

@router.post("/smtp/test", response_model=SmtpTestResponse)
async def test_smtp_connection(
    settings_data: SmtpSettings,
    current_user: User = Depends(get_current_user_from_jwt)
) -> SmtpTestResponse:
    """Test SMTP connection with provided settings"""
    try:
        # Test SMTP connection
        try:
            if settings_data.security == "SSL":
                server = smtplib.SMTP_SSL(settings_data.server, settings_data.port)
            else:
                server = smtplib.SMTP(settings_data.server, settings_data.port)
                if settings_data.security == "TLS":
                    server.starttls()
            
            server.login(settings_data.username, settings_data.password)
            server.quit()
            
            # Update stored settings with connection status
            settings_dict = settings_data.dict()
            settings_dict["isConnected"] = True
            save_setting("smtp", settings_dict, current_user.id)
            
            return SmtpTestResponse(success=True, error=None)
            
        except Exception as smtp_error:
            return SmtpTestResponse(success=False, error=str(smtp_error))
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test SMTP connection: {str(e)}"
        )

@router.get("/account", response_model=AccountSettingsResponse)
async def get_account_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> AccountSettingsResponse:
    """Get account configuration settings"""
    try:
        default_settings = {
            "organizationName": "",
            "contactEmail": "",
            "timezone": "UTC",
            "language": "English"
        }
        
        stored_settings = load_setting("account", default_settings, current_user.id)
        
        return AccountSettingsResponse(**stored_settings)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get account settings: {str(e)}"
        )

@router.put("/account", response_model=AccountSettingsResponse)
async def update_account_settings(
    settings_data: AccountSettings,
    current_user: User = Depends(get_current_user_from_jwt)
) -> AccountSettingsResponse:
    """Update account configuration settings"""
    try:
        settings_dict = settings_data.dict()
        save_setting("account", settings_dict, current_user.id)
        
        return AccountSettingsResponse(**settings_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update account settings: {str(e)}"
        )

@router.get("/security", response_model=SecuritySettingsResponse)
async def get_security_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> SecuritySettingsResponse:
    """Get security configuration settings"""
    try:
        default_settings = {
            "twoFactorEnabled": False,
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30
        }
        
        stored_settings = load_setting("security", default_settings, current_user.id)
        
        return SecuritySettingsResponse(**stored_settings)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get security settings: {str(e)}"
        )

@router.post("/security/2fa")
async def toggle_two_factor_auth(
    request: Dict[str, bool],
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, bool]:
    """Toggle two-factor authentication"""
    try:
        current_settings = load_setting("security", {
            "twoFactorEnabled": False,
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30
        }, current_user.id)
        
        current_settings["twoFactorEnabled"] = request.get("enabled", False)
        save_setting("security", current_settings, current_user.id)
        
        return {"enabled": current_settings["twoFactorEnabled"]}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle 2FA: {str(e)}"
        )

@router.post("/security/api-rotation")
async def toggle_api_key_rotation(
    request: Dict[str, bool],
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, bool]:
    """Toggle API key rotation"""
    try:
        current_settings = load_setting("security", {
            "twoFactorEnabled": False,
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30
        }, current_user.id)
        
        current_settings["apiKeyRotationEnabled"] = request.get("enabled", False)
        save_setting("security", current_settings, current_user.id)
        
        return {"enabled": current_settings["apiKeyRotationEnabled"]}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle API rotation: {str(e)}"
        )

@router.put("/security/session-timeout")
async def update_session_timeout(
    request: Dict[str, int],
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, str]:
    """Update session timeout"""
    try:
        current_settings = load_setting("security", {
            "twoFactorEnabled": False,
            "apiKeyRotationEnabled": False,
            "sessionTimeout": 30
        }, current_user.id)
        
        current_settings["sessionTimeout"] = request.get("timeout", 30)
        save_setting("security", current_settings, current_user.id)
        
        return {"message": "Session timeout updated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session timeout: {str(e)}"
        )

@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> NotificationSettingsResponse:
    """Get notification settings"""
    try:
        default_settings = {
            "campaignCompletion": True,
            "highBounceRate": True,
            "apiLimitWarnings": True,
            "securityAlerts": True,
            "weeklyReports": False,
            "webhookUrl": "",
            "emailNotifications": True
        }
        
        stored_settings = load_setting("notifications", default_settings, current_user.id)
        
        return NotificationSettingsResponse(**stored_settings)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get notification settings: {str(e)}"
        )

@router.put("/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings_data: NotificationSettings,
    current_user: User = Depends(get_current_user_from_jwt)
) -> NotificationSettingsResponse:
    """Update notification settings"""
    try:
        settings_dict = settings_data.dict()
        save_setting("notifications", settings_dict, current_user.id)
        
        return NotificationSettingsResponse(**settings_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update notification settings: {str(e)}"
        )

@router.get("/storage", response_model=StorageResponse)
async def get_storage_data(
    current_user: User = Depends(get_current_user_from_jwt)
) -> StorageResponse:
    """Get storage usage data"""
    try:
        # Mock storage data - in production, calculate from actual usage
        default_data = {
            "used": 0.5,
            "total": 10.0,
            "retentionPeriod": 12
        }
        
        stored_data = load_setting("storage", default_data, current_user.id)
        
        return StorageResponse(**stored_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage data: {str(e)}"
        )

@router.put("/storage/retention")
async def update_retention_period(
    request: Dict[str, int],
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, str]:
    """Update data retention period"""
    try:
        current_data = load_setting("storage", {
            "used": 0.5,
            "total": 10.0,
            "retentionPeriod": 12
        }, current_user.id)
        
        current_data["retentionPeriod"] = request.get("months", 12)
        save_setting("storage", current_data, current_user.id)
        
        return {"message": "Retention period updated"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update retention period: {str(e)}"
        )

@router.post("/data/export")
async def export_data(
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, str]:
    """Export user data"""
    try:
        # Mock export - in production, create actual export file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"emailtracker_export_{current_user.id}_{timestamp}.json"
        download_url = f"{app_settings.base_url}/exports/{filename}"
        
        return {
            "filename": filename,
            "downloadUrl": download_url,
            "message": "Export prepared"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export data: {str(e)}"
        )

@router.delete("/data/delete")
async def delete_all_data(
    current_user: User = Depends(get_current_user_from_jwt)
) -> Dict[str, str]:
    """Delete all user data"""
    try:
        # Clear all settings for this API key
        keys_to_remove = [key for key in _settings_store.keys() if key.endswith(f":{current_user.id}")]
        for key in keys_to_remove:
            del _settings_store[key]
        
        # Reset storage data
        save_setting("storage", {
            "used": 0.0,
            "total": 10.0,
            "retentionPeriod": 12
        }, current_user.id)
        
        return {"message": "All data deleted successfully"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete data: {str(e)}"
        )

@router.get("/domains", response_model=DomainSettingsResponse)
async def get_domain_settings(
    current_user: User = Depends(get_current_user_from_jwt)
) -> DomainSettingsResponse:
    """Get domain configuration settings"""
    try:
        default_settings = {
            "trackingDomain": "",
            "sendingDomain": ""
        }
        
        stored_settings = load_setting("domains", default_settings, current_user.id)
        
        return DomainSettingsResponse(**stored_settings)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain settings: {str(e)}"
        )

@router.put("/domains", response_model=DomainSettingsResponse)
async def update_domain_settings(
    settings_data: DomainSettings,
    current_user: User = Depends(get_current_user_from_jwt)
) -> DomainSettingsResponse:
    """Update domain configuration settings"""
    try:
        settings_dict = settings_data.dict()
        save_setting("domains", settings_dict, current_user.id)
        
        return DomainSettingsResponse(**settings_dict)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update domain settings: {str(e)}"
        )

@router.get("/domains/status", response_model=DomainStatusResponse)
async def get_domain_status(
    current_user: User = Depends(get_current_user_from_jwt)
) -> DomainStatusResponse:
    """Get domain DNS verification status"""
    try:
        # Mock status - in production, actually check DNS records
        default_status = {
            "spf": "pending",
            "dkim": "pending"
        }
        
        stored_status = load_setting("domain_status", default_status, current_user.id)
        
        return DomainStatusResponse(**stored_status)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get domain status: {str(e)}"
        )

@router.post("/domains/verify", response_model=DomainStatusResponse)
async def verify_dns_records(
    current_user: User = Depends(get_current_user_from_jwt)
) -> DomainStatusResponse:
    """Verify DNS records for domains"""
    try:
        # Mock verification - in production, actually verify DNS
        import random
        statuses = ["verified", "pending", "failed"]
        
        verified_status = {
            "spf": random.choice(statuses),
            "dkim": random.choice(statuses)
        }
        
        save_setting("domain_status", verified_status, current_user.id)
        
        return DomainStatusResponse(**verified_status)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify DNS records: {str(e)}"
        )
