"""
Production-ready authentication middleware and error handling

Provides comprehensive authentication debugging and clean error responses.
"""
from fastapi import HTTPException, status
from functools import wraps
import logging
from typing import Callable, Any

logger = logging.getLogger("auth.middleware")


def auth_error_handler(func: Callable) -> Callable:
    """
    Decorator to provide clean authentication error handling
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except HTTPException as e:
            # Re-raise HTTP exceptions as-is
            raise e
        except Exception as e:
            logger.error(f"Authentication error in {func.__name__}: {str(e)}")
            
            # Convert generic exceptions to clean 401 responses
            if "token" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired authentication token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            elif "api key" in str(e).lower() or "api_key" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or missing API key"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed",
                    headers={"WWW-Authenticate": "Bearer"}
                )
    
    return wrapper


def create_auth_response_headers(auth_method: str) -> dict:
    """
    Create appropriate WWW-Authenticate headers based on auth method
    """
    if auth_method == "jwt":
        return {"WWW-Authenticate": "Bearer"}
    elif auth_method == "api_key":
        return {"WWW-Authenticate": "ApiKey"}
    else:
        return {"WWW-Authenticate": "Bearer"}


class AuthConfig:
    """
    Centralized authentication configuration
    """
    
    # JWT Configuration
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    # API Key Configuration
    API_KEY_HEADER_NAME = "x-api-key"
    API_KEY_MAX_KEYS_PER_USER = 10
    API_KEY_DEFAULT_RATE_LIMIT = 100  # per minute
    
    # Security Configuration
    REQUIRE_EMAIL_VERIFICATION = True
    ENABLE_SESSION_TRACKING = True
    LOG_AUTH_ATTEMPTS = True
    
    @classmethod
    def get_error_messages(cls) -> dict:
        """Get standardized error messages"""
        return {
            "jwt_required": "JWT token required for dashboard access",
            "jwt_invalid": "Invalid or expired JWT token",
            "jwt_user_inactive": "User account is inactive",
            "jwt_user_unverified": "Email verification required",
            
            "api_key_required": "API key required. Include 'x-api-key' header.",
            "api_key_invalid": "Invalid API key",
            "api_key_inactive": "API key is deactivated",
            "api_key_expired": "API key has expired",
            "api_key_scope_missing": "API key does not have required permissions",
            
            "generic_auth_failed": "Authentication failed",
            "generic_access_denied": "Access denied"
        }


# Utility functions for common authentication patterns
def require_verified_user(user):
    """Check if user is verified and raise appropriate error if not"""
    if not user.is_verified and AuthConfig.REQUIRE_EMAIL_VERIFICATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=AuthConfig.get_error_messages()["jwt_user_unverified"]
        )


def require_active_user(user):
    """Check if user is active and raise appropriate error if not"""
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=AuthConfig.get_error_messages()["jwt_user_inactive"]
        )
