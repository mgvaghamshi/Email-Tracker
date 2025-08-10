"""
Settings schema definitions
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from datetime import datetime


class SmtpSettings(BaseModel):
    server: str
    port: int
    security: Literal["TLS", "SSL", "NONE"]
    username: str
    password: str
    isConnected: bool = False


class SmtpSettingsResponse(BaseModel):
    server: str
    port: int
    security: Literal["TLS", "SSL", "NONE"]
    username: str
    password: str
    isConnected: bool


class SmtpTestResponse(BaseModel):
    success: bool
    error: Optional[str] = None


class AccountSettings(BaseModel):
    organizationName: str
    contactEmail: EmailStr
    timezone: str
    language: str


class AccountSettingsResponse(BaseModel):
    organizationName: str
    contactEmail: str
    timezone: str
    language: str


class SecuritySettings(BaseModel):
    twoFactorEnabled: bool
    apiKeyRotationEnabled: bool
    sessionTimeout: int


class SecuritySettingsResponse(BaseModel):
    twoFactorEnabled: bool
    apiKeyRotationEnabled: bool
    sessionTimeout: int


class NotificationSettings(BaseModel):
    campaignCompletion: bool
    highBounceRate: bool
    apiLimitWarnings: bool
    securityAlerts: bool
    weeklyReports: bool
    webhookUrl: Optional[str] = ""
    emailNotifications: bool


class NotificationSettingsResponse(BaseModel):
    campaignCompletion: bool
    highBounceRate: bool
    apiLimitWarnings: bool
    securityAlerts: bool
    weeklyReports: bool
    webhookUrl: Optional[str] = ""
    emailNotifications: bool


class StorageData(BaseModel):
    used: float
    total: float
    retentionPeriod: int


class StorageResponse(BaseModel):
    used: float
    total: float
    retentionPeriod: int


class DomainSettings(BaseModel):
    trackingDomain: str
    sendingDomain: str


class DomainSettingsResponse(BaseModel):
    trackingDomain: str
    sendingDomain: str


class DomainStatusResponse(BaseModel):
    spf: Literal["verified", "pending", "failed"]
    dkim: Literal["verified", "pending", "failed"]
