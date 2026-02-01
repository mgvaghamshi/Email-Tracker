"""
Defaults Integration Examples
Shows how to integrate the defaults system with existing services
"""

# Example 1: User Registration Service Integration
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..services.defaults_manager import get_defaults_manager
from ..services.defaults_seeder import get_defaults_seeder
from ..database.user_models import User
from ..core.logging_config import get_logger

logger = get_logger("services.user_registration_enhanced")


class EnhancedUserRegistrationService:
    """Enhanced user registration with defaults seeding"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
        self.defaults_seeder = get_defaults_seeder(db_session)
    
    async def register_user(
        self,
        email: str,
        full_name: str,
        password: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Register a new user with default configurations"""
        
        try:
            # 1. Create the user account (existing logic)
            user = User(
                email=email,
                full_name=full_name,
                # ... other user fields
            )
            self.db.add(user)
            self.db.flush()  # Get the user ID
            
            user_id = str(user.id)
            
            # 2. Seed user-specific defaults
            logger.info(f"Seeding defaults for new user: {user_id}")
            defaults_result = await self.defaults_seeder.seed_user_defaults(
                user_id=user_id,
                tenant_id=tenant_id
            )
            
            # 3. Get user's effective preferences
            user_preferences = self.defaults_manager.get_user_defaults_by_category(
                user_id, "account_preferences"
            )
            
            # 4. Apply preferences to user account
            if user_preferences:
                # Email preferences
                email_prefs = user_preferences.get("email", {})
                user.email_notifications = email_prefs.get("notifications_enabled", True)
                user.marketing_emails = email_prefs.get("marketing_enabled", False)
                
                # UI preferences
                ui_prefs = user_preferences.get("ui", {})
                user.theme = ui_prefs.get("theme", "light")
                user.language = ui_prefs.get("language", "en")
                user.timezone = ui_prefs.get("timezone", "UTC")
            
            # 5. Set up default subscription plan
            plan_defaults = self.defaults_manager.get_global_default(
                "subscription_plans", "default_plan"
            )
            if plan_defaults:
                # Create user subscription with default plan
                from ..database.subscription_models import UserSubscription
                subscription = UserSubscription(
                    user_id=user.id,
                    plan_name=plan_defaults.get("name", "free"),
                    status="active"
                )
                self.db.add(subscription)
            
            self.db.commit()
            
            logger.info(f"User registration completed with {defaults_result['created']} defaults seeded")
            
            return {
                "success": True,
                "user_id": user_id,
                "defaults_seeded": defaults_result["created"],
                "preferences_applied": bool(user_preferences)
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"User registration failed: {e}")
            raise


# Example 2: Campaign Creation Service Integration
class EnhancedCampaignService:
    """Enhanced campaign service with defaults support"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
    
    async def create_campaign(
        self,
        user_id: str,
        name: str,
        subject: str,
        template_id: Optional[int] = None,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create a campaign with user and global defaults"""
        
        try:
            # 1. Get campaign defaults for user
            campaign_defaults = self.defaults_manager.get_user_defaults_by_category(
                user_id, "campaign_settings"
            )
            
            # 2. Get email delivery defaults
            delivery_defaults = self.defaults_manager.get_user_default(
                user_id, "email_delivery", "smtp_settings"
            )
            
            # 3. Get analytics defaults
            analytics_defaults = self.defaults_manager.get_user_default(
                user_id, "analytics", "tracking"
            )
            
            # 4. Build campaign configuration
            campaign_config = {
                # Base settings
                "name": name,
                "subject": subject,
                "user_id": user_id,
                "template_id": template_id,
                
                # Apply defaults
                "timezone": campaign_defaults.get("timezone", "UTC"),
                "send_rate": campaign_defaults.get("send_rate", 100),
                "retry_failed": campaign_defaults.get("retry_failed", True),
                
                # Delivery settings
                "smtp_settings": delivery_defaults or {},
                
                # Analytics settings
                "track_opens": analytics_defaults.get("enable_open_tracking", True),
                "track_clicks": analytics_defaults.get("enable_click_tracking", True),
                "track_bounces": analytics_defaults.get("enable_bounce_tracking", True),
                
                # Override with custom settings
                **(custom_settings or {})
            }
            
            # 5. Create campaign with merged settings
            from ..database.campaign_models import Campaign
            campaign = Campaign(**campaign_config)
            self.db.add(campaign)
            self.db.commit()
            
            logger.info(f"Campaign created with defaults applied: {campaign.id}")
            
            return {
                "success": True,
                "campaign_id": campaign.id,
                "defaults_applied": {
                    "campaign_settings": bool(campaign_defaults),
                    "delivery_settings": bool(delivery_defaults),
                    "analytics_settings": bool(analytics_defaults)
                }
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Campaign creation failed: {e}")
            raise


# Example 3: Settings API Integration
class SettingsAPIService:
    """Settings API enhanced with defaults system"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
    
    def get_user_settings(self, user_id: str, category: Optional[str] = None) -> Dict[str, Any]:
        """Get user settings with defaults fallback"""
        
        try:
            if category:
                # Get specific category with defaults
                settings = self.defaults_manager.get_user_defaults_by_category(user_id, category)
                
                # Include metadata about value sources
                detailed_settings = {}
                for key, value in settings.items():
                    hierarchy = {
                        "global": self.defaults_manager.get_global_default(category, key),
                        "user": self.defaults_manager.get_user_default_direct(user_id, category, key),
                        "effective": value
                    }
                    
                    source = "user" if hierarchy["user"] is not None else "global"
                    
                    detailed_settings[key] = {
                        "value": value,
                        "source": source,
                        "hierarchy": hierarchy
                    }
                
                return {
                    "category": category,
                    "settings": detailed_settings
                }
            else:
                # Get all user settings
                all_settings = self.defaults_manager.get_all_user_defaults(user_id)
                return {
                    "settings": all_settings,
                    "categories": list(all_settings.keys())
                }
                
        except Exception as e:
            logger.error(f"Error getting user settings: {e}")
            raise
    
    def update_user_setting(
        self,
        user_id: str,
        category: str,
        key: str,
        value: Any,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a user setting"""
        
        try:
            # Get current value for comparison
            current_value = self.defaults_manager.get_user_default(user_id, category, key)
            
            # Update the setting
            success = self.defaults_manager.set_user_default(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                description=description
            )
            
            if success:
                return {
                    "success": True,
                    "category": category,
                    "key": key,
                    "old_value": current_value,
                    "new_value": value,
                    "message": f"Setting {category}.{key} updated successfully"
                }
            else:
                raise Exception("Failed to update setting")
                
        except Exception as e:
            logger.error(f"Error updating user setting: {e}")
            raise
    
    def reset_user_setting(self, user_id: str, category: str, key: str) -> Dict[str, Any]:
        """Reset a user setting to its default value"""
        
        try:
            # Get current values
            current_value = self.defaults_manager.get_user_default(user_id, category, key)
            global_default = self.defaults_manager.get_global_default(category, key)
            
            # Delete user-specific override
            success = self.defaults_manager.delete_user_default(user_id, category, key)
            
            if success:
                # Get new effective value
                new_value = self.defaults_manager.get_user_default(user_id, category, key)
                
                return {
                    "success": True,
                    "category": category,
                    "key": key,
                    "old_value": current_value,
                    "new_value": new_value,
                    "reset_to": "global_default" if global_default is not None else "none",
                    "message": f"Setting {category}.{key} reset to default"
                }
            else:
                raise Exception("Failed to reset setting")
                
        except Exception as e:
            logger.error(f"Error resetting user setting: {e}")
            raise


# Example 4: Tenant Onboarding Integration
class TenantOnboardingService:
    """Service for onboarding new tenants with defaults"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
        self.defaults_seeder = get_defaults_seeder(db_session)
    
    async def onboard_tenant(
        self,
        tenant_id: str,
        tenant_name: str,
        admin_user_id: str,
        custom_settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Onboard a new tenant with full defaults setup"""
        
        try:
            # 1. Seed tenant-specific defaults
            logger.info(f"Onboarding tenant: {tenant_id}")
            tenant_result = await self.defaults_seeder.seed_tenant_defaults(tenant_id)
            
            # 2. Apply custom settings if provided
            if custom_settings:
                for category, settings in custom_settings.items():
                    for key, value in settings.items():
                        self.defaults_manager.set_tenant_default(
                            tenant_id=tenant_id,
                            category=category,
                            key=key,
                            value=value
                        )
            
            # 3. Set up tenant admin user defaults
            admin_result = await self.defaults_seeder.seed_user_defaults(
                user_id=admin_user_id,
                tenant_id=tenant_id
            )
            
            # 4. Create tenant-specific configurations
            branding_defaults = self.defaults_manager.get_tenant_defaults_by_category(
                tenant_id, "branding"
            )
            
            # 5. Set up initial templates and campaigns based on defaults
            template_defaults = self.defaults_manager.get_global_default(
                "email_templates", "system_templates"
            )
            
            result = {
                "success": True,
                "tenant_id": tenant_id,
                "tenant_defaults_seeded": tenant_result["created"],
                "admin_defaults_seeded": admin_result["created"],
                "branding_configured": bool(branding_defaults),
                "templates_available": bool(template_defaults)
            }
            
            logger.info(f"Tenant onboarding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Tenant onboarding failed: {e}")
            raise


# Example 5: Analytics Service Integration
class EnhancedAnalyticsService:
    """Analytics service with configurable defaults"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
    
    def get_analytics_config(self, user_id: str) -> Dict[str, Any]:
        """Get analytics configuration for a user"""
        
        try:
            # Get all analytics defaults for user
            analytics_config = self.defaults_manager.get_user_defaults_by_category(
                user_id, "analytics"
            )
            
            return {
                "tracking": analytics_config.get("tracking", {}),
                "retention": analytics_config.get("retention", {}),
                "reporting": analytics_config.get("reporting", {}),
                "performance": analytics_config.get("performance", {})
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics config: {e}")
            raise
    
    def should_track_event(self, user_id: str, event_type: str) -> bool:
        """Check if an event type should be tracked for a user"""
        
        try:
            tracking_config = self.defaults_manager.get_user_default(
                user_id, "analytics", "tracking"
            )
            
            if not tracking_config:
                return True  # Default to tracking if no config
            
            tracking_map = {
                "open": tracking_config.get("enable_open_tracking", True),
                "click": tracking_config.get("enable_click_tracking", True),
                "delivery": tracking_config.get("enable_delivery_tracking", True),
                "bounce": tracking_config.get("enable_bounce_tracking", True)
            }
            
            return tracking_map.get(event_type, True)
            
        except Exception as e:
            logger.error(f"Error checking tracking config: {e}")
            return True  # Default to tracking on error
