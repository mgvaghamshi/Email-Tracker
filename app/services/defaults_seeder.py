"""
Defaults Seeding Service
Handles initial seeding and ongoing updates of default configurations
"""
import os
import yaml
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from .defaults_manager import DefaultsManager, get_defaults_manager
from ..database.subscription_models import create_default_plans, DEFAULT_PLANS, SUBSCRIPTION_FEATURES
from ..database.user_models import Role
from ..services.user_onboarding import create_default_templates_for_user
from ..core.logging_config import get_logger

logger = get_logger("services.defaults_seeder")


class DefaultsSeeder:
    """Handles seeding of all default configurations"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.defaults_manager = get_defaults_manager(db_session)
        
    async def seed_all_defaults(self) -> Dict[str, Any]:
        """Seed all default configurations"""
        logger.info("Starting comprehensive defaults seeding")
        
        results = {
            "global_defaults": 0,
            "subscription_plans": 0,
            "system_roles": 0,
            "system_templates": 0,
            "security_policies": 0,
            "email_delivery": 0,
            "analytics_defaults": 0,
            "compliance_settings": 0,
            "errors": [],
            "total_seeded": 0
        }
        
        try:
            # 1. Load global defaults from configuration files
            config_results = self.defaults_manager.load_defaults_from_config()
            results["global_defaults"] = config_results.get("global", 0)
            
            # 2. Seed subscription plans
            plans_result = await self.seed_subscription_plans()
            results["subscription_plans"] = plans_result["created"]
            
            # 3. Seed system roles and permissions
            roles_result = await self.seed_system_roles()
            results["system_roles"] = roles_result["created"]
            
            # 4. Seed system templates
            templates_result = await self.seed_system_templates()
            results["system_templates"] = templates_result["created"]
            
            # 5. Seed specific configuration categories
            security_result = await self.seed_security_policies()
            results["security_policies"] = security_result["created"]
            
            email_result = await self.seed_email_delivery_defaults()
            results["email_delivery"] = email_result["created"]
            
            analytics_result = await self.seed_analytics_defaults()
            results["analytics_defaults"] = analytics_result["created"]
            
            compliance_result = await self.seed_compliance_settings()
            results["compliance_settings"] = compliance_result["created"]
            
            # Calculate total
            results["total_seeded"] = sum([
                results["global_defaults"],
                results["subscription_plans"],
                results["system_roles"],
                results["system_templates"],
                results["security_policies"],
                results["email_delivery"],
                results["analytics_defaults"],
                results["compliance_settings"]
            ])
            
            logger.info(f"Completed defaults seeding: {results['total_seeded']} items seeded")
            return results
            
        except Exception as e:
            logger.error(f"Error during comprehensive seeding: {e}")
            results["errors"].append(str(e))
            return results
    
    async def seed_subscription_plans(self) -> Dict[str, Any]:
        """Seed subscription plans from configuration"""
        logger.info("Seeding subscription plans")
        
        result = {
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        try:
            # Use existing function but also store in defaults system
            create_default_plans(self.db)
            
            # Store plan configurations in defaults system for easy management
            for plan_config in DEFAULT_PLANS:
                success = self.defaults_manager.set_global_default(
                    category="subscription_plans",
                    key=f"plans.{plan_config['name']}",
                    value=plan_config,
                    description=f"Configuration for {plan_config['display_name']} subscription plan"
                )
                
                if success:
                    result["created"] += 1
                else:
                    result["errors"].append(f"Failed to store plan config: {plan_config['name']}")
            
            # Store feature definitions
            success = self.defaults_manager.set_global_default(
                category="subscription_plans",
                key="features",
                value=SUBSCRIPTION_FEATURES,
                description="All available subscription features and their descriptions"
            )
            
            if success:
                result["created"] += 1
            
            # Store plan upgrade matrix
            upgrade_matrix = {
                "free": {
                    "recommended_upgrade": "pro",
                    "upgrade_triggers": ["campaigns_limit_reached", "recipients_limit_reached"],
                    "upgrade_benefits": ["Unlimited campaigns", "10x more recipients", "Advanced analytics"]
                },
                "pro": {
                    "recommended_upgrade": "enterprise",
                    "upgrade_triggers": ["team_size_growth", "compliance_requirements"],
                    "upgrade_benefits": ["Team collaboration", "Advanced security", "White labeling"]
                }
            }
            
            success = self.defaults_manager.set_global_default(
                category="subscription_plans",
                key="upgrade_matrix",
                value=upgrade_matrix,
                description="Plan upgrade recommendations and benefits"
            )
            
            if success:
                result["created"] += 1
            
            logger.info(f"Subscription plans seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding subscription plans: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_system_roles(self) -> Dict[str, Any]:
        """Seed default system roles and permissions"""
        logger.info("Seeding system roles")
        
        result = {
            "created": 0,
            "updated": 0,
            "errors": []
        }
        
        try:
            # Define default system roles
            default_roles = [
                {
                    "name": "admin",
                    "display_name": "Administrator",
                    "description": "Full system access and user management",
                    "permissions": [
                        "admin:read", "admin:write", "admin:delete",
                        "users:read", "users:write", "users:delete",
                        "roles:read", "roles:write", "roles:delete",
                        "campaigns:read", "campaigns:write", "campaigns:delete",
                        "contacts:read", "contacts:write", "contacts:delete",
                        "templates:read", "templates:write", "templates:delete",
                        "analytics:read", "analytics:write",
                        "settings:read", "settings:write",
                        "api_keys:read", "api_keys:write", "api_keys:delete"
                    ],
                    "is_system": True
                },
                {
                    "name": "user",
                    "display_name": "User",
                    "description": "Standard user with basic permissions",
                    "permissions": [
                        "campaigns:read", "campaigns:write",
                        "contacts:read", "contacts:write",
                        "templates:read", "templates:write",
                        "analytics:read",
                        "api_keys:read", "api_keys:write"
                    ],
                    "is_system": True
                },
                {
                    "name": "moderator",
                    "display_name": "Moderator",
                    "description": "User management and content moderation",
                    "permissions": [
                        "users:read", "users:write",
                        "campaigns:read", "campaigns:write", "campaigns:delete",
                        "contacts:read", "contacts:write",
                        "templates:read", "templates:write",
                        "analytics:read"
                    ],
                    "is_system": True
                },
                {
                    "name": "viewer",
                    "display_name": "Viewer",
                    "description": "Read-only access to campaigns and analytics",
                    "permissions": [
                        "campaigns:read",
                        "contacts:read",
                        "templates:read",
                        "analytics:read"
                    ],
                    "is_system": True
                }
            ]
            
            # Create roles in database
            for role_config in default_roles:
                existing_role = self.db.query(Role).filter(
                    Role.name == role_config["name"]
                ).first()
                
                if not existing_role:
                    import json
                    role = Role(
                        name=role_config["name"],
                        display_name=role_config["display_name"],
                        description=role_config["description"],
                        permissions=json.dumps(role_config["permissions"]),
                        is_system=role_config["is_system"]
                    )
                    self.db.add(role)
                    result["created"] += 1
                else:
                    # Update existing role
                    import json
                    existing_role.display_name = role_config["display_name"]
                    existing_role.description = role_config["description"]
                    existing_role.permissions = json.dumps(role_config["permissions"])
                    result["updated"] += 1
            
            self.db.commit()
            
            # Store role configurations in defaults system
            success = self.defaults_manager.set_global_default(
                category="user_management",
                key="default_roles",
                value=default_roles,
                description="Default system roles and their permissions"
            )
            
            if success:
                result["created"] += 1
            
            # Store permission definitions
            permission_definitions = {
                "admin:read": "View admin interface and system information",
                "admin:write": "Modify system settings and configurations",
                "admin:delete": "Delete system data and configurations",
                "users:read": "View user accounts and profiles",
                "users:write": "Create and modify user accounts",
                "users:delete": "Delete user accounts",
                "roles:read": "View roles and permissions",
                "roles:write": "Create and modify roles",
                "roles:delete": "Delete roles",
                "campaigns:read": "View email campaigns",
                "campaigns:write": "Create and modify campaigns",
                "campaigns:delete": "Delete campaigns",
                "contacts:read": "View contact lists",
                "contacts:write": "Create and modify contacts",
                "contacts:delete": "Delete contacts",
                "templates:read": "View email templates",
                "templates:write": "Create and modify templates",
                "templates:delete": "Delete templates",
                "analytics:read": "View analytics and reports",
                "analytics:write": "Modify analytics settings",
                "settings:read": "View system settings",
                "settings:write": "Modify system settings",
                "api_keys:read": "View API keys",
                "api_keys:write": "Create and modify API keys",
                "api_keys:delete": "Delete API keys"
            }
            
            success = self.defaults_manager.set_global_default(
                category="user_management",
                key="permissions",
                value=permission_definitions,
                description="All available permissions and their descriptions"
            )
            
            if success:
                result["created"] += 1
            
            logger.info(f"System roles seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding system roles: {e}")
            self.db.rollback()
            result["errors"].append(str(e))
            return result
    
    async def seed_system_templates(self) -> Dict[str, Any]:
        """Seed default system email templates"""
        logger.info("Seeding system templates")
        
        result = {
            "created": 0,
            "errors": []
        }
        
        try:
            # Create a dummy user for template creation
            from ..database.user_models import User
            dummy_user = User(
                email="system@example.com",
                full_name="System",
                is_active=False  # This is just for template creation
            )
            
            # Create default templates (they will be system templates)
            templates = create_default_templates_for_user(dummy_user, self.db)
            result["created"] = len(templates)
            
            # Store template configurations in defaults
            template_configs = {
                "welcome_email": {
                    "type": "welcome",
                    "subject": "Welcome to {{company_name}}!",
                    "description": "Default welcome email for new users",
                    "is_system": True
                },
                "monthly_newsletter": {
                    "type": "newsletter",
                    "subject": "{{company_name}} - {{month}} Newsletter",
                    "description": "Default monthly newsletter template",
                    "is_system": True
                }
            }
            
            success = self.defaults_manager.set_global_default(
                category="email_templates",
                key="system_templates",
                value=template_configs,
                description="Default system email template configurations"
            )
            
            if success:
                result["created"] += 1
            
            logger.info(f"System templates seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding system templates: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_tenant_defaults(self, tenant_id: str) -> Dict[str, Any]:
        """Seed defaults for a new tenant"""
        logger.info(f"Seeding tenant defaults for {tenant_id}")
        
        result = {
            "tenant_id": tenant_id,
            "created": 0,
            "errors": []
        }
        
        try:
            # Load tenant default configurations
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "../../config/defaults/tenant"
            )
            
            if os.path.exists(config_path):
                for yaml_file in os.listdir(config_path):
                    if yaml_file.endswith('.yaml'):
                        category = yaml_file.replace('_defaults.yaml', '').replace('.yaml', '')
                        
                        with open(os.path.join(config_path, yaml_file), 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        # Store tenant-specific defaults
                        for key, value in config_data.items():
                            success = self.defaults_manager.set_tenant_default(
                                tenant_id=tenant_id,
                                category=category,
                                key=key,
                                value=value
                            )
                            
                            if success:
                                result["created"] += 1
            
            logger.info(f"Tenant defaults seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding tenant defaults: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_user_defaults(self, user_id: str, tenant_id: str = None) -> Dict[str, Any]:
        """Seed defaults for a new user"""
        logger.info(f"Seeding user defaults for {user_id}")
        
        result = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "created": 0,
            "errors": []
        }
        
        try:
            # Load user default configurations
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "../../config/defaults/user"
            )
            
            if os.path.exists(config_path):
                for yaml_file in os.listdir(config_path):
                    if yaml_file.endswith('.yaml'):
                        category = yaml_file.replace('.yaml', '')
                        
                        with open(os.path.join(config_path, yaml_file), 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        # Store user-specific defaults
                        for key, value in config_data.items():
                            success = self.defaults_manager.set_user_default(
                                user_id=user_id,
                                category=category,
                                key=key,
                                value=value
                            )
                            
                            if success:
                                result["created"] += 1
            
            logger.info(f"User defaults seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding user defaults: {e}")
            result["errors"].append(str(e))
            return result
            
    async def seed_security_policies(self) -> Dict[str, Any]:
        """Seed security policy defaults"""
        logger.info("Seeding security policies")
        
        result = {
            "created": 0,
            "errors": []
        }
        
        try:
            # Load security policies from YAML if available
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "../../config/defaults/global/security_policies.yaml"
            )
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    security_config = yaml.safe_load(f)
                
                # Store each section as a separate setting
                for section, config in security_config.items():
                    success = self.defaults_manager.set_global_default(
                        category="security_policies",
                        key=section,
                        value=config,
                        description=f"Security policies for {section}"
                    )
                    
                    if success:
                        result["created"] += 1
            
            logger.info(f"Security policies seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding security policies: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_email_delivery_defaults(self) -> Dict[str, Any]:
        """Seed email delivery defaults"""
        logger.info("Seeding email delivery defaults")
        
        result = {
            "created": 0,
            "errors": []
        }
        
        try:
            # Load email delivery configuration
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "../../config/defaults/global/email_delivery.yaml"
            )
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    email_config = yaml.safe_load(f)
                
                # Store each section as a separate setting
                for section, config in email_config.items():
                    success = self.defaults_manager.set_global_default(
                        category="email_delivery",
                        key=section,
                        value=config,
                        description=f"Email delivery settings for {section}"
                    )
                    
                    if success:
                        result["created"] += 1
            
            logger.info(f"Email delivery defaults seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding email delivery defaults: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_analytics_defaults(self) -> Dict[str, Any]:
        """Seed analytics and tracking defaults"""
        logger.info("Seeding analytics defaults")
        
        result = {
            "created": 0,
            "errors": []
        }
        
        try:
            analytics_config = {
                "tracking": {
                    "enable_open_tracking": True,
                    "enable_click_tracking": True,
                    "enable_delivery_tracking": True,
                    "enable_bounce_tracking": True,
                    "bot_detection_enabled": True,
                    "tracking_pixel_cache_hours": 24
                },
                "retention": {
                    "raw_events_days": 90,
                    "aggregated_data_days": 365,
                    "campaign_data_days": 1095  # 3 years
                },
                "reporting": {
                    "real_time_updates": True,
                    "batch_processing_interval": 300,  # 5 minutes
                    "automated_reports": False,
                    "weekly_digest": False,
                    "monthly_summary": False
                },
                "performance": {
                    "aggregation_batch_size": 1000,
                    "query_timeout_seconds": 30,
                    "cache_ttl_seconds": 300,
                    "enable_query_optimization": True
                }
            }
            
            for section, config in analytics_config.items():
                success = self.defaults_manager.set_global_default(
                    category="analytics",
                    key=section,
                    value=config,
                    description=f"Analytics settings for {section}"
                )
                
                if success:
                    result["created"] += 1
            
            logger.info(f"Analytics defaults seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding analytics defaults: {e}")
            result["errors"].append(str(e))
            return result
    
    async def seed_compliance_settings(self) -> Dict[str, Any]:
        """Seed compliance and regulatory defaults"""
        logger.info("Seeding compliance settings")
        
        result = {
            "created": 0,
            "errors": []
        }
        
        try:
            compliance_config = {
                "gdpr": {
                    "enabled": True,
                    "consent_required": True,
                    "data_portability": True,
                    "right_to_be_forgotten": True,
                    "cookie_consent": True,
                    "lawful_basis": "consent",
                    "data_retention_days": 2555  # 7 years
                },
                "can_spam": {
                    "enabled": True,
                    "require_physical_address": True,
                    "require_unsubscribe_link": True,
                    "honor_unsubscribe_immediately": True,
                    "include_sender_info": True
                },
                "ccpa": {
                    "enabled": True,
                    "opt_out_enabled": True,
                    "do_not_sell": True,
                    "consumer_request_processing_days": 45
                },
                "casl": {
                    "enabled": False,
                    "explicit_consent_required": True,
                    "business_relationship_exemption": True
                },
                "audit": {
                    "log_all_consent": True,
                    "log_all_unsubscribes": True,
                    "log_data_access": True,
                    "audit_retention_years": 7
                }
            }
            
            for section, config in compliance_config.items():
                success = self.defaults_manager.set_global_default(
                    category="compliance",
                    key=section,
                    value=config,
                    description=f"Compliance settings for {section}"
                )
                
                if success:
                    result["created"] += 1
            
            logger.info(f"Compliance settings seeding completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error seeding compliance settings: {e}")
            result["errors"].append(str(e))
            return result


# Factory function
def get_defaults_seeder(db_session: Session) -> DefaultsSeeder:
    """Factory function to create a DefaultsSeeder instance"""
    return DefaultsSeeder(db_session)
