"""
Configuration management for EmailTracker API
"""
import os
import json
import logging
from typing import Optional, List
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure basic logging for config warnings
logger = logging.getLogger("app.config")


class Settings(BaseModel):
    """Application settings with environment-specific configurations"""
    
    # Application Settings
    app_name: str = os.getenv("APP_NAME", "EmailTracker API")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    app_description: str = "Professional email sending and tracking service - like Mailgun"
    environment: str = os.getenv("ENVIRONMENT", "development")
    debug: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # API Configuration
    api_v1_prefix: str = os.getenv("API_V1_PREFIX", "/api/v1")
    base_url: str = os.getenv("BASE_URL", "http://localhost:8001")
    port: int = int(os.getenv("PORT", "8001"))
    
    # Database Configuration
    database_url: str = "sqlite:///./email_tracker.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    
    # Redis Configuration (for caching and performance)
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_enabled: bool = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    cache_ttl: int = int(os.getenv("CACHE_TTL", "300"))  # 5 minutes default
    cache_enabled: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    
    # Performance Configuration
    enable_query_optimization: bool = os.getenv("ENABLE_QUERY_OPTIMIZATION", "true").lower() == "true"
    sqlite_optimization: bool = os.getenv("SQLITE_OPTIMIZATION", "true").lower() == "true"
    background_task_workers: int = int(os.getenv("BACKGROUND_TASK_WORKERS", "4"))
    max_connections_per_pool: int = int(os.getenv("MAX_CONNECTIONS_PER_POOL", "20"))
    
    # Security Configuration
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    api_key: str = os.getenv("API_KEY", "emailtracker-api-key-dev")
    
    # SMTP Configuration
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_username: str = os.getenv("SMTP_USERNAME", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_use_tls: bool = os.getenv("SMTP_USE_TLS", "True").lower() == "true"
    smtp_use_ssl: bool = os.getenv("SMTP_USE_SSL", "False").lower() == "true"
    verify_ssl: bool = os.getenv("VERIFY_SSL", "True").lower() == "true"
    
    # Email Defaults
    default_from_email: str = os.getenv("DEFAULT_FROM_EMAIL", "noreply@example.com")
    default_from_name: str = os.getenv("DEFAULT_FROM_NAME", "EmailTracker")
    sender_name: str = os.getenv("SENDER_NAME", "EmailTracker")
    
    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600
    
    # CORS Configuration
    cors_origins: List[str] = ["*"]
    
    # Tracking & Analytics
    tracking_pixel_enabled: bool = True
    bot_detection_enabled: bool = True
    tracking_pixel_cache_seconds: int = 3600
    
    # Feature Flags
    enable_docs: bool = True
    enable_redoc: bool = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_from_environment()
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        # Application settings
        self.environment = os.getenv("ENVIRONMENT", self.environment)
        self.debug = os.getenv("DEBUG", str(self.debug)).lower() == "true"
        self.base_url = os.getenv("BASE_URL", self.base_url)
        self.secret_key = os.getenv("SECRET_KEY", self.secret_key)
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", self.database_url)
        
        # SMTP
        self.smtp_server = os.getenv("SMTP_SERVER", self.smtp_server)
        self.smtp_port = int(os.getenv("SMTP_PORT", str(self.smtp_port)))
        self.smtp_username = os.getenv("SMTP_USERNAME", self.smtp_username)
        self.smtp_password = os.getenv("SMTP_PASSWORD", self.smtp_password)
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", str(self.smtp_use_tls)).lower() == "true"
        
        # Email defaults
        self.default_from_email = os.getenv("DEFAULT_FROM_EMAIL", self.default_from_email)
        self.default_from_name = os.getenv("DEFAULT_FROM_NAME", self.default_from_name)
        self.sender_name = os.getenv("SENDER_NAME", self.sender_name)
        
        # Rate limiting
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", str(self.rate_limit_enabled)).lower() == "true"
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", str(self.rate_limit_requests)))
        
        # CORS (handle JSON string)
        cors_origins_env = os.getenv("CORS_ORIGINS")
        if cors_origins_env:
            try:
                self.cors_origins = json.loads(cors_origins_env)
            except json.JSONDecodeError:
                # Fallback to comma-separated string
                self.cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]
        
        # Features
        self.enable_docs = os.getenv("ENABLE_DOCS", str(self.enable_docs)).lower() == "true"
        self.enable_redoc = os.getenv("ENABLE_REDOC", str(self.enable_redoc)).lower() == "true"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment"""
        return self.environment == "staging"


# Global settings instance
settings = Settings()
import os
import json
from typing import Optional, List, Union
from pydantic import BaseModel, field_validator


class Settings(BaseModel):
    """Application settings with environment-specific configurations"""
    
    # =================================================================
    # Application Settings
    # =================================================================
    app_name: str = "EmailTracker API"
    app_version: str = "1.0.0"
    app_description: str = "Professional email sending and tracking service - like Mailgun"
    environment: str = "development"
    debug: bool = True
    
    # API Configuration
    api_v1_prefix: str = "/api/v1"
    base_url: str = "http://localhost:8001"
    
    # =================================================================
    # Database Configuration
    # =================================================================
    database_url: str = "sqlite:///./email_tracker.db"
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    
    # =================================================================
    # Security Configuration
    # =================================================================
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # =================================================================
    # SMTP Configuration
    # =================================================================
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    verify_ssl: bool = True
    
    # Email Defaults
    default_from_email: str = "noreply@example.com"
    default_from_name: str = "EmailTracker"
    sender_name: str = "EmailTracker"
    
    # =================================================================
    # External Email Services
    # =================================================================
    sendgrid_api_key: Optional[str] = None
    mailgun_api_key: Optional[str] = None
    mailgun_domain: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    # =================================================================
    # Redis Configuration
    # =================================================================
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    redis_db: int = 0
    redis_max_connections: int = 10
    
    # =================================================================
    # Rate Limiting
    # =================================================================
    rate_limit_enabled: bool = True
    rate_limit_requests: int = 100
    rate_limit_period: int = 3600
    rate_limit_burst: int = 10
    api_key_rate_limit_per_minute: int = 60
    api_key_rate_limit_per_day: int = 10000
    
    # =================================================================
    # CORS Configuration
    # =================================================================
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:3100"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    # =================================================================
    # Tracking & Analytics
    # =================================================================
    tracking_pixel_enabled: bool = True
    tracking_links_enabled: bool = True
    bot_detection_enabled: bool = True
    tracking_pixel_cache_seconds: int = 3600
    analytics_retention_days: int = 90
    analytics_batch_size: int = 1000
    
    # External Analytics
    google_analytics_id: Optional[str] = None
    sentry_dsn: Optional[str] = None
    
    # =================================================================
    # Logging Configuration
    # =================================================================
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    log_requests: bool = True
    log_responses: bool = False
    log_sql_queries: bool = False
    
    # =================================================================
    # Performance Settings
    # =================================================================
    worker_timeout: int = 30
    worker_connections: int = 1000
    max_requests: int = 1000
    max_requests_jitter: int = 50
    health_check_interval: int = 30
    health_check_timeout: int = 5
    
    # =================================================================
    # Feature Flags
    # =================================================================
    feature_webhooks_enabled: bool = True
    feature_bulk_email_enabled: bool = True
    feature_campaign_analytics: bool = True
    feature_email_templates: bool = True
    feature_scheduled_emails: bool = True
    
    # =================================================================
    # Development Settings
    # =================================================================
    reload_on_change: bool = True
    debug_sql: bool = False
    debug_redis: bool = False
    debug_smtp: bool = False
    enable_profiler: bool = False
    enable_docs: bool = True
    enable_redoc: bool = True
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_from_environment()
        self._validate_environment_specific_settings()
    
    def _load_from_environment(self):
        """Load configuration from environment variables"""
        # Application settings
        self.environment = os.getenv("ENVIRONMENT", self.environment)
        self.debug = os.getenv("DEBUG", str(self.debug)).lower() == "true"
        self.base_url = os.getenv("BASE_URL", self.base_url)
        self.secret_key = os.getenv("SECRET_KEY", self.secret_key)
        
        # Database
        self.database_url = os.getenv("DATABASE_URL", self.database_url)
        self.db_pool_size = int(os.getenv("DB_POOL_SIZE", self.db_pool_size))
        self.db_max_overflow = int(os.getenv("DB_MAX_OVERFLOW", self.db_max_overflow))
        
        # SMTP
        self.smtp_server = os.getenv("SMTP_SERVER", self.smtp_server)
        self.smtp_port = int(os.getenv("SMTP_PORT", self.smtp_port))
        self.smtp_username = os.getenv("SMTP_USERNAME", self.smtp_username)
        self.smtp_password = os.getenv("SMTP_PASSWORD", self.smtp_password)
        self.smtp_use_tls = os.getenv("SMTP_USE_TLS", str(self.smtp_use_tls)).lower() == "true"
        
        # Email defaults
        self.default_from_email = os.getenv("DEFAULT_FROM_EMAIL", self.default_from_email)
        self.default_from_name = os.getenv("DEFAULT_FROM_NAME", self.default_from_name)
        self.sender_name = os.getenv("SENDER_NAME", self.sender_name)
        
        # External services
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
        self.mailgun_api_key = os.getenv("MAILGUN_API_KEY")
        self.mailgun_domain = os.getenv("MAILGUN_DOMAIN")
        
        # Redis
        self.redis_url = os.getenv("REDIS_URL", self.redis_url)
        self.redis_password = os.getenv("REDIS_PASSWORD")
        
        # Rate limiting
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", str(self.rate_limit_enabled)).lower() == "true"
        self.rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", self.rate_limit_requests))
        
        # CORS (handle JSON string)
        cors_origins_env = os.getenv("CORS_ORIGINS")
        if cors_origins_env:
            try:
                self.cors_origins = json.loads(cors_origins_env)
            except json.JSONDecodeError:
                # Fallback to comma-separated string
                self.cors_origins = [origin.strip() for origin in cors_origins_env.split(",")]
        
        # Analytics
        self.google_analytics_id = os.getenv("GOOGLE_ANALYTICS_ID")
        self.sentry_dsn = os.getenv("SENTRY_DSN")
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.log_file = os.getenv("LOG_FILE")
        
        # Features
        self.feature_webhooks_enabled = os.getenv("FEATURE_WEBHOOKS_ENABLED", str(self.feature_webhooks_enabled)).lower() == "true"
        self.enable_docs = os.getenv("ENABLE_DOCS", str(self.enable_docs)).lower() == "true"
    
    def _validate_environment_specific_settings(self):
        """Validate settings based on environment"""
        if self.environment == "production":
            # Production validations
            if self.secret_key == "dev-secret-key-change-in-production":
                raise ValueError("SECRET_KEY must be changed for production environment")
            
            if self.debug:
                logger.warning("Debug mode is enabled in production environment")
            
            if "sqlite" in self.database_url.lower():
                logger.warning("Using SQLite in production is not recommended")
            
            if not self.smtp_username or not self.smtp_password:
                logger.warning("SMTP credentials not configured for production")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment"""
        return self.environment == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == "production"
    
    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment"""
        return self.environment == "staging"


# Global settings instance
settings = Settings()
