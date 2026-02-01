"""
Two-Factor Authentication models for EmailTracker API
"""
import uuid
import secrets
import base64
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from .models import Base
from typing import List, Optional
import pyotp
import qrcode
import io


class TwoFactorAuth(Base):
    """Two-Factor Authentication model for TOTP-based 2FA"""
    __tablename__ = "two_factor_auth"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # TOTP Secret (base32 encoded)
    secret = Column(String, nullable=False)  # Base32 encoded secret for TOTP
    
    # Status and verification
    is_enabled = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)  # Has user verified setup?
    
    # Backup codes
    backup_codes_hash = Column(Text, nullable=True)  # JSON array of hashed backup codes
    backup_codes_used = Column(Text, nullable=True)  # JSON array of used backup codes
    
    # QR Code and setup
    qr_code_generated_at = Column(DateTime, nullable=True)
    setup_completed_at = Column(DateTime, nullable=True)
    
    # Last usage
    last_used_at = Column(DateTime, nullable=True)
    last_code_used = Column(String, nullable=True)  # Prevent code reuse
    
    # Recovery and security
    recovery_codes_generated_at = Column(DateTime, nullable=True)
    failed_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="two_factor_auth")
    attempts = relationship("TwoFactorAttempt", back_populates="two_factor_auth", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_2fa_user_id', 'user_id'),
        Index('idx_2fa_enabled', 'is_enabled'),
        Index('idx_2fa_verified', 'is_verified'),
    )
    
    @classmethod
    def generate_secret(cls) -> str:
        """Generate a new TOTP secret"""
        return pyotp.random_base32()
    
    def get_totp(self) -> pyotp.TOTP:
        """Get TOTP instance for this secret"""
        return pyotp.TOTP(self.secret)
    
    def get_provisioning_uri(self, user_email: str, issuer_name: str = "EmailTracker") -> str:
        """Get provisioning URI for QR code generation"""
        return self.get_totp().provisioning_uri(
            name=user_email,
            issuer_name=issuer_name
        )
    
    def generate_qr_code(self, user_email: str, issuer_name: str = "EmailTracker") -> bytes:
        """Generate QR code image for TOTP setup"""
        uri = self.get_provisioning_uri(user_email, issuer_name)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        self.qr_code_generated_at = datetime.utcnow()
        
        return img_io.getvalue()
    
    def verify_code(self, code: str, allow_reuse: bool = False) -> bool:
        """Verify a TOTP code"""
        if not self.is_enabled:
            return False
        
        # Check if locked due to failed attempts
        if self.locked_until and self.locked_until > datetime.utcnow():
            return False
        
        # Prevent code reuse
        if not allow_reuse and self.last_code_used == code:
            return False
        
        # Verify the code
        totp = self.get_totp()
        if totp.verify(code, valid_window=1):  # Allow 1 window tolerance
            self.last_used_at = datetime.utcnow()
            self.last_code_used = code
            self.failed_attempts = 0
            self.locked_until = None
            return True
        
        # Handle failed attempt
        self.failed_attempts += 1
        if self.failed_attempts >= 5:
            self.locked_until = datetime.utcnow() + timedelta(minutes=15)
        
        return False
    
    def generate_backup_codes(self, count: int = 8) -> List[str]:
        """Generate backup codes for recovery"""
        import bcrypt
        import json
        
        codes = []
        hashed_codes = []
        
        for _ in range(count):
            code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
            codes.append(code)
            hashed_codes.append(bcrypt.hashpw(code.encode('utf-8'), bcrypt.gensalt()).decode('utf-8'))
        
        self.backup_codes_hash = json.dumps(hashed_codes)
        self.backup_codes_used = json.dumps([])
        self.recovery_codes_generated_at = datetime.utcnow()
        
        return codes
    
    def verify_backup_code(self, code: str) -> bool:
        """Verify and consume a backup code"""
        import bcrypt
        import json
        
        if not self.backup_codes_hash:
            return False
        
        hashed_codes = json.loads(self.backup_codes_hash)
        used_codes = json.loads(self.backup_codes_used or '[]')
        
        for i, hashed_code in enumerate(hashed_codes):
            if i in used_codes:
                continue
                
            if bcrypt.checkpw(code.encode('utf-8'), hashed_code.encode('utf-8')):
                # Mark as used
                used_codes.append(i)
                self.backup_codes_used = json.dumps(used_codes)
                self.last_used_at = datetime.utcnow()
                self.failed_attempts = 0
                self.locked_until = None
                return True
        
        return False
    
    def get_backup_codes_remaining(self) -> int:
        """Get number of unused backup codes"""
        import json
        
        if not self.backup_codes_hash:
            return 0
        
        hashed_codes = json.loads(self.backup_codes_hash)
        used_codes = json.loads(self.backup_codes_used or '[]')
        
        return len(hashed_codes) - len(used_codes)
    
    def reset_2fa(self):
        """Reset 2FA settings (disable and clear data)"""
        self.is_enabled = False
        self.is_verified = False
        self.backup_codes_hash = None
        self.backup_codes_used = None
        self.last_code_used = None
        self.failed_attempts = 0
        self.locked_until = None
        self.setup_completed_at = None
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<TwoFactorAuth(id={self.id}, user_id={self.user_id}, enabled={self.is_enabled})>"


class TwoFactorAttempt(Base):
    """Two-Factor Authentication attempt tracking"""
    __tablename__ = "two_factor_attempts"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    two_factor_auth_id = Column(String, ForeignKey("two_factor_auth.id"), nullable=False)
    
    # Attempt details
    code_type = Column(String, nullable=False)  # 'totp', 'backup'
    success = Column(Boolean, nullable=False)
    failure_reason = Column(String, nullable=True)  # 'invalid_code', 'code_reuse', 'locked', etc.
    
    # Request metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timing
    attempted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    two_factor_auth = relationship("TwoFactorAuth", back_populates="attempts")
    
    __table_args__ = (
        Index('idx_2fa_attempt_2fa_id', 'two_factor_auth_id'),
        Index('idx_2fa_attempt_success', 'success'),
        Index('idx_2fa_attempt_attempted_at', 'attempted_at'),
        Index('idx_2fa_attempt_ip', 'ip_address'),
    )


class TwoFactorSession(Base):
    """Temporary 2FA session for multi-step authentication"""
    __tablename__ = "two_factor_sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Session information
    session_token = Column(String, unique=True, nullable=False)  # Temporary token for 2FA flow
    
    # What the user is trying to do
    purpose = Column(String, nullable=False)  # 'login', 'setup', 'disable', 'recovery'
    
    # Status
    is_verified = Column(Boolean, default=False)
    is_consumed = Column(Boolean, default=False)
    
    # Request metadata
    ip_address = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    verified_at = Column(DateTime, nullable=True)
    consumed_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_2fa_session_user_id', 'user_id'),
        Index('idx_2fa_session_token', 'session_token'),
        Index('idx_2fa_session_expires_at', 'expires_at'),
        Index('idx_2fa_session_purpose', 'purpose'),
    )
    
    @classmethod
    def generate_session_token(cls) -> str:
        """Generate a secure session token"""
        return secrets.token_urlsafe(32)
    
    def is_valid(self) -> bool:
        """Check if session is valid and not expired"""
        return (
            not self.is_consumed and 
            self.expires_at > datetime.utcnow()
        )
    
    def mark_verified(self):
        """Mark session as verified"""
        self.is_verified = True
        self.verified_at = datetime.utcnow()
    
    def consume(self):
        """Mark session as consumed"""
        self.is_consumed = True
        self.consumed_at = datetime.utcnow()
