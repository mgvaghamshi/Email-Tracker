"""
Decorators and middleware for subscription tier-based access control
"""
from functools import wraps
from fastapi import HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, List, Callable, Any

from ..database.user_models import User
from ..services.subscription_service import get_user_access_service
from ..dependencies import get_db


def require_feature(feature: str, error_message: Optional[str] = None):
    """
    Decorator to require a specific feature for endpoint access.
    
    Args:
        feature: The feature name to check (e.g., 'ab_testing', 'segmentation')
        error_message: Custom error message if access is denied
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user and db from the function arguments/kwargs
            current_user = None
            db = None
            
            # Look for current_user and db in kwargs (FastAPI dependency injection)
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif hasattr(value, 'query'):  # SQLAlchemy Session
                    db = value
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Missing user or database session"
                )
            
            # Check feature access
            access_service = get_user_access_service(current_user.id, db)
            
            if not access_service.has_feature(feature):
                plan_name = access_service.get_plan_display_name()
                
                default_message = f"This feature requires a higher subscription tier. Current plan: {plan_name}"
                message = error_message or default_message
                
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "feature_access_denied",
                        "message": message,
                        "required_feature": feature,
                        "current_plan": plan_name,
                        "upgrade_required": True
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_plan(required_plan: str, error_message: Optional[str] = None):
    """
    Decorator to require a specific subscription plan or higher.
    
    Args:
        required_plan: The minimum plan required ('free', 'pro', 'enterprise')
        error_message: Custom error message if access is denied
    """
    plan_hierarchy = {'free': 0, 'pro': 1, 'enterprise': 2}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user and db from the function arguments/kwargs
            current_user = None
            db = None
            
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif hasattr(value, 'query'):  # SQLAlchemy Session
                    db = value
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Missing user or database session"
                )
            
            # Check plan level
            access_service = get_user_access_service(current_user.id, db)
            current_plan = access_service.get_plan_name()
            
            current_level = plan_hierarchy.get(current_plan, 0)
            required_level = plan_hierarchy.get(required_plan, 0)
            
            if current_level < required_level:
                default_message = f"This feature requires {required_plan.title()} plan or higher. Current plan: {access_service.get_plan_display_name()}"
                message = error_message or default_message
                
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "plan_upgrade_required",
                        "message": message,
                        "current_plan": current_plan,
                        "required_plan": required_plan,
                        "upgrade_required": True
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def check_usage_limit(limit_type: str, count: int = 1, error_message: Optional[str] = None):
    """
    Decorator to check usage limits before executing endpoint.
    
    Args:
        limit_type: Type of limit to check ('campaigns', 'recipients', 'emails', 'templates', 'contacts')
        count: Number of units to check against the limit
        error_message: Custom error message if limit is exceeded
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user and db from the function arguments/kwargs
            current_user = None
            db = None
            
            for key, value in kwargs.items():
                if isinstance(value, User):
                    current_user = value
                elif hasattr(value, 'query'):  # SQLAlchemy Session
                    db = value
            
            if not current_user or not db:
                raise HTTPException(
                    status_code=500,
                    detail="Internal error: Missing user or database session"
                )
            
            # Check usage limit
            access_service = get_user_access_service(current_user.id, db)
            
            # Map limit types to service methods
            limit_checks = {
                'campaigns': access_service.can_create_campaign,
                'templates': access_service.can_create_template,
                'emails': lambda: access_service.can_send_monthly_emails(count),
                'contacts': lambda: access_service.can_add_contacts(count),
                'recipients': lambda: access_service.can_send_to_recipients(count)
            }
            
            if limit_type not in limit_checks:
                raise HTTPException(
                    status_code=500,
                    detail=f"Unknown limit type: {limit_type}"
                )
            
            can_proceed = limit_checks[limit_type]()
            
            if not can_proceed:
                usage_stats = access_service.get_usage_stats()
                current_usage = usage_stats.get('usage', {}).get(limit_type, {})
                
                used = current_usage.get('used', 0)
                limit = current_usage.get('limit', 'unlimited')
                
                default_message = f"Usage limit exceeded for {limit_type}. Used: {used}, Limit: {limit}"
                message = error_message or default_message
                
                raise HTTPException(
                    status_code=429,  # Too Many Requests
                    detail={
                        "error": "usage_limit_exceeded",
                        "message": message,
                        "limit_type": limit_type,
                        "current_usage": used,
                        "limit": limit,
                        "plan": access_service.get_plan_display_name(),
                        "upgrade_required": True
                    }
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def track_usage(feature_name: str, count: int = 1):
    """
    Decorator to track feature usage after successful endpoint execution.
    
    Args:
        feature_name: Name of the feature being used
        count: Number of units used
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute the original function first
            result = await func(*args, **kwargs)
            
            # Track usage after successful execution
            try:
                # Extract current_user and db from the function arguments/kwargs
                current_user = None
                db = None
                
                for key, value in kwargs.items():
                    if isinstance(value, User):
                        current_user = value
                    elif hasattr(value, 'query'):  # SQLAlchemy Session
                        db = value
                
                if current_user and db:
                    access_service = get_user_access_service(current_user.id, db)
                    
                    # Map feature names to tracking methods
                    tracking_methods = {
                        'campaign_create': access_service.track_campaign_creation,
                        'email_send': lambda: access_service.track_email_sent(count),
                        'template_create': access_service.track_template_creation,
                        'contact_add': lambda: access_service.track_contact_addition(count)
                    }
                    
                    if feature_name in tracking_methods:
                        tracking_methods[feature_name]()
                    else:
                        # Generic usage logging
                        access_service._log_usage(feature_name, count)
            
            except Exception as e:
                # Log the error but don't fail the request
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to track usage for {feature_name}: {str(e)}")
            
            return result
        return wrapper
    return decorator


# Combined decorators for common use cases
def require_pro_feature(feature: str, error_message: Optional[str] = None):
    """Convenience decorator that combines plan and feature checks for Pro features"""
    def decorator(func: Callable) -> Callable:
        # Apply both decorators
        func = require_plan('pro', f"This feature requires Pro plan or higher")(func)
        func = require_feature(feature, error_message)(func)
        return func
    return decorator


def require_enterprise_feature(feature: str, error_message: Optional[str] = None):
    """Convenience decorator that combines plan and feature checks for Enterprise features"""
    def decorator(func: Callable) -> Callable:
        # Apply both decorators
        func = require_plan('enterprise', f"This feature requires Enterprise plan")(func)
        func = require_feature(feature, error_message)(func)
        return func
    return decorator


# Middleware functions for FastAPI dependencies
async def get_feature_access_service(
    current_user: User = Depends(),
    db: Session = Depends(get_db)
):
    """FastAPI dependency to get FeatureAccessService"""
    return get_user_access_service(current_user.id, db)


def create_feature_checker(feature: str):
    """Factory function to create feature-checking dependencies"""
    async def check_feature_access(
        access_service = Depends(get_feature_access_service)
    ):
        if not access_service.has_feature(feature):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_access_denied",
                    "message": f"This feature requires a higher subscription tier",
                    "required_feature": feature,
                    "current_plan": access_service.get_plan_display_name(),
                    "upgrade_required": True
                }
            )
        return True
    
    return check_feature_access


def create_plan_checker(required_plan: str):
    """Factory function to create plan-checking dependencies"""
    plan_hierarchy = {'free': 0, 'pro': 1, 'enterprise': 2}
    
    async def check_plan_access(
        access_service = Depends(get_feature_access_service)
    ):
        current_plan = access_service.get_plan_name()
        current_level = plan_hierarchy.get(current_plan, 0)
        required_level = plan_hierarchy.get(required_plan, 0)
        
        if current_level < required_level:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "plan_upgrade_required",
                    "message": f"This feature requires {required_plan.title()} plan or higher",
                    "current_plan": current_plan,
                    "required_plan": required_plan,
                    "upgrade_required": True
                }
            )
        return True
    
    return check_plan_access


# Pre-created common dependencies
require_pro_plan = create_plan_checker('pro')
require_enterprise_plan = create_plan_checker('enterprise')
require_ab_testing = create_feature_checker('ab_testing')
require_segmentation = create_feature_checker('segmentation')
require_ai_features = create_feature_checker('ai_content_generation')
