"""
Authentication module for EmailTracker API

Separates JWT-based dashboard authentication from API key-based programmatic access.
"""

# Import main authentication dependencies for easy access
from .jwt_auth import (
    get_current_user_from_jwt,
    get_current_active_user_from_jwt,
    get_current_verified_user_from_jwt,
    get_optional_user_from_jwt
)

from .api_key_auth import (
    get_user_from_api_key,
    get_user_and_api_key,
    check_api_key_permission,
    require_api_key_scope,
    get_optional_user_from_api_key
)

from .middleware import (
    AuthConfig,
    require_verified_user,
    require_active_user
)

# Export all authentication functions
__all__ = [
    # JWT Authentication (Dashboard/Frontend)
    "get_current_user_from_jwt",
    "get_current_active_user_from_jwt",
    "get_current_verified_user_from_jwt",
    "get_optional_user_from_jwt",
    
    # API Key Authentication (External/Programmatic)
    "get_user_from_api_key",
    "get_user_and_api_key",
    "check_api_key_permission",
    "require_api_key_scope",
    "get_optional_user_from_api_key",
    
    # Middleware
    "AuthConfig",
    "require_verified_user",
    "require_active_user"
]
