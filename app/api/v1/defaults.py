"""
Defaults Management API Endpoints
Provides REST API for managing default configurations
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

from ..database.database import get_db
from ..services.defaults_manager import get_defaults_manager
from ..services.defaults_seeder import get_defaults_seeder
from ..auth.auth_utils import get_current_user
from ..database.user_models import User
from ..core.logging_config import get_logger

logger = get_logger("api.defaults")

router = APIRouter(prefix="/api/defaults", tags=["defaults"])


# Pydantic models for request/response
class DefaultValue(BaseModel):
    """Model for a default configuration value"""
    category: str = Field(..., description="Configuration category")
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    value_type: Optional[str] = Field(None, description="Value type (string, int, bool, json)")
    description: Optional[str] = Field(None, description="Description of this setting")


class DefaultsResponse(BaseModel):
    """Response model for defaults data"""
    success: bool
    data: Dict[str, Any]
    message: Optional[str] = None


class SeedRequest(BaseModel):
    """Request model for seeding defaults"""
    categories: Optional[List[str]] = Field(None, description="Categories to seed (all if not specified)")
    force: bool = Field(False, description="Force re-seeding existing values")
    dry_run: bool = Field(False, description="Preview changes without applying them")


class SeedResponse(BaseModel):
    """Response model for seeding operation"""
    success: bool
    results: Dict[str, Any]
    message: str


# Global defaults endpoints
@router.get("/global", response_model=DefaultsResponse)
async def get_global_defaults(
    category: Optional[str] = Query(None, description="Filter by category"),
    key: Optional[str] = Query(None, description="Filter by key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get global default configurations"""
    try:
        defaults_manager = get_defaults_manager(db)
        
        if category and key:
            # Get specific default
            value = defaults_manager.get_global_default(category, key)
            if value is None:
                raise HTTPException(status_code=404, detail="Default not found")
            return DefaultsResponse(
                success=True,
                data={f"{category}.{key}": value}
            )
        elif category:
            # Get all defaults for category
            defaults = defaults_manager.get_global_defaults_by_category(category)
            return DefaultsResponse(
                success=True,
                data=defaults
            )
        else:
            # Get all global defaults
            defaults = defaults_manager.get_all_global_defaults()
            return DefaultsResponse(
                success=True,
                data=defaults
            )
    
    except Exception as e:
        logger.error(f"Error getting global defaults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/global", response_model=DefaultsResponse)
async def set_global_default(
    default: DefaultValue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set a global default configuration value"""
    try:
        # Check if user has admin permissions
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        defaults_manager = get_defaults_manager(db)
        
        success = defaults_manager.set_global_default(
            category=default.category,
            key=default.key,
            value=default.value,
            description=default.description
        )
        
        if success:
            return DefaultsResponse(
                success=True,
                data={f"{default.category}.{default.key}": default.value},
                message="Global default set successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to set global default")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting global default: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/global/{category}/{key}")
async def delete_global_default(
    category: str,
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a global default configuration"""
    try:
        # Check if user has admin permissions
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        defaults_manager = get_defaults_manager(db)
        
        success = defaults_manager.delete_global_default(category, key)
        
        if success:
            return {"success": True, "message": "Global default deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Default not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting global default: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# User-specific defaults endpoints
@router.get("/user", response_model=DefaultsResponse)
async def get_user_defaults(
    category: Optional[str] = Query(None, description="Filter by category"),
    key: Optional[str] = Query(None, description="Filter by key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user-specific default configurations"""
    try:
        defaults_manager = get_defaults_manager(db)
        user_id = str(current_user.id)
        
        if category and key:
            # Get specific default with hierarchical lookup
            value = defaults_manager.get_user_default(user_id, category, key)
            if value is None:
                raise HTTPException(status_code=404, detail="Default not found")
            return DefaultsResponse(
                success=True,
                data={f"{category}.{key}": value}
            )
        elif category:
            # Get all defaults for category
            defaults = defaults_manager.get_user_defaults_by_category(user_id, category)
            return DefaultsResponse(
                success=True,
                data=defaults
            )
        else:
            # Get all user defaults
            defaults = defaults_manager.get_all_user_defaults(user_id)
            return DefaultsResponse(
                success=True,
                data=defaults
            )
    
    except Exception as e:
        logger.error(f"Error getting user defaults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/user", response_model=DefaultsResponse)
async def set_user_default(
    default: DefaultValue,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Set a user-specific default configuration value"""
    try:
        defaults_manager = get_defaults_manager(db)
        user_id = str(current_user.id)
        
        success = defaults_manager.set_user_default(
            user_id=user_id,
            category=default.category,
            key=default.key,
            value=default.value,
            description=default.description
        )
        
        if success:
            return DefaultsResponse(
                success=True,
                data={f"{default.category}.{default.key}": default.value},
                message="User default set successfully"
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to set user default")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting user default: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/user/{category}/{key}")
async def delete_user_default(
    category: str,
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user-specific default configuration"""
    try:
        defaults_manager = get_defaults_manager(db)
        user_id = str(current_user.id)
        
        success = defaults_manager.delete_user_default(user_id, category, key)
        
        if success:
            return {"success": True, "message": "User default deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Default not found")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user default: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Bulk operations
@router.get("/categories")
async def get_available_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all available configuration categories"""
    try:
        defaults_manager = get_defaults_manager(db)
        categories = defaults_manager.get_all_categories()
        
        return {
            "success": True,
            "categories": categories,
            "count": len(categories)
        }
    
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hierarchy/{category}/{key}")
async def get_default_hierarchy(
    category: str,
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get the full hierarchy for a specific default (global -> tenant -> user)"""
    try:
        defaults_manager = get_defaults_manager(db)
        user_id = str(current_user.id)
        
        hierarchy = {
            "global": defaults_manager.get_global_default(category, key),
            "user": defaults_manager.get_user_default_direct(user_id, category, key),
            "effective": defaults_manager.get_user_default(user_id, category, key)
        }
        
        return {
            "success": True,
            "category": category,
            "key": key,
            "hierarchy": hierarchy
        }
    
    except Exception as e:
        logger.error(f"Error getting default hierarchy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Seeding endpoints
@router.post("/seed", response_model=SeedResponse)
async def seed_defaults(
    request: SeedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Seed default configurations"""
    try:
        # Check if user has admin permissions
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        seeder = get_defaults_seeder(db)
        
        if request.dry_run:
            # For dry run, return what would be seeded
            available_categories = [
                "subscription_plans", "system_roles", "system_templates",
                "security_policies", "email_delivery", "analytics_defaults",
                "compliance_settings"
            ]
            
            categories_to_seed = request.categories or available_categories
            
            return SeedResponse(
                success=True,
                results={
                    "dry_run": True,
                    "categories_to_seed": categories_to_seed,
                    "total_categories": len(categories_to_seed)
                },
                message=f"[DRY RUN] Would seed {len(categories_to_seed)} categories"
            )
        
        # Run actual seeding
        if request.categories:
            # Seed specific categories
            results = {"categories": {}, "total_seeded": 0, "errors": []}
            
            for category in request.categories:
                try:
                    if category == "subscription_plans":
                        result = await seeder.seed_subscription_plans()
                    elif category == "system_roles":
                        result = await seeder.seed_system_roles()
                    elif category == "system_templates":
                        result = await seeder.seed_system_templates()
                    elif category == "security_policies":
                        result = await seeder.seed_security_policies()
                    elif category == "email_delivery":
                        result = await seeder.seed_email_delivery_defaults()
                    elif category == "analytics_defaults":
                        result = await seeder.seed_analytics_defaults()
                    elif category == "compliance_settings":
                        result = await seeder.seed_compliance_settings()
                    else:
                        results["errors"].append(f"Unknown category: {category}")
                        continue
                    
                    results["categories"][category] = result
                    results["total_seeded"] += result.get("created", 0)
                    
                except Exception as e:
                    results["errors"].append(f"{category}: {str(e)}")
            
        else:
            # Seed all defaults
            results = await seeder.seed_all_defaults()
        
        success = len(results.get("errors", [])) == 0
        message = f"Seeded {results.get('total_seeded', 0)} defaults"
        
        if results.get("errors"):
            message += f" with {len(results['errors'])} errors"
        
        return SeedResponse(
            success=success,
            results=results,
            message=message
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error seeding defaults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check(
    db: Session = Depends(get_db)
):
    """Health check for defaults management system"""
    try:
        defaults_manager = get_defaults_manager(db)
        
        # Try to get a simple default to test the system
        test_categories = defaults_manager.get_all_categories()
        
        return {
            "success": True,
            "message": "Defaults management system is healthy",
            "categories_count": len(test_categories),
            "timestamp": defaults_manager._get_current_time().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "success": False,
            "message": f"Defaults management system is unhealthy: {str(e)}",
            "error": str(e)
        }
