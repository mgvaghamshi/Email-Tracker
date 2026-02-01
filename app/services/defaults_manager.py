"""
Centralized Defaults Management Service
Handles the three-tier defaults system: Global -> Tenant -> User
"""
import os
import yaml
import json
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, Text, Boolean, DateTime, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid
from pathlib import Path

from ..database.models import Base
from ..core.logging_config import get_logger

logger = get_logger("services.defaults_manager")


# Database models for storing defaults
class GlobalDefault(Base):
    """Global system-wide defaults"""
    __tablename__ = "global_defaults"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    category = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False)
    schema_version = Column(String, default="1.0")
    is_overridable = Column(Boolean, default=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_global_defaults_category', 'category'),
        Index('idx_global_defaults_key', 'key'),
        Index('idx_global_defaults_category_key', 'category', 'key'),
    )


class TenantDefault(Base):
    """Tenant-specific defaults"""
    __tablename__ = "tenant_defaults"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, nullable=False)  # Will link to tenant table when multi-tenancy is added
    category = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False)
    inherits_from_global = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tenant_defaults_tenant', 'tenant_id'),
        Index('idx_tenant_defaults_category', 'category'),
        Index('idx_tenant_defaults_key', 'key'),
        Index('idx_tenant_defaults_tenant_category_key', 'tenant_id', 'category', 'key'),
    )


class UserDefault(Base):
    """User-specific defaults"""
    __tablename__ = "user_defaults"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    category = Column(String, nullable=False)
    key = Column(String, nullable=False)
    value = Column(JSON, nullable=False)
    inherits_from_tenant = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_defaults_user', 'user_id'),
        Index('idx_user_defaults_category', 'category'),
        Index('idx_user_defaults_key', 'key'),
        Index('idx_user_defaults_user_category_key', 'user_id', 'category', 'key'),
    )


class DefaultsManager:
    """
    Centralized defaults management service
    Implements the three-tier inheritance system: Global -> Tenant -> User
    """
    
    def __init__(self, db_session: Session, config_path: str = None):
        self.db = db_session
        self.config_path = config_path or os.path.join(os.path.dirname(__file__), "../../config/defaults")
        self._cache = {}
        self._cache_ttl = 300  # 5 minutes
        
    def get_setting(self, 
                   key: str, 
                   category: str = None,
                   user_id: str = None, 
                   tenant_id: str = None,
                   default: Any = None) -> Any:
        """
        Get effective setting value with inheritance hierarchy
        Priority: User -> Tenant -> Global -> Default
        """
        try:
            # Parse category.key if provided as single string
            if '.' in key and category is None:
                category, key = key.split('.', 1)
            
            # Try user-specific setting first
            if user_id:
                user_setting = self._get_user_setting(user_id, category, key)
                if user_setting is not None:
                    logger.debug(f"Found user setting for {category}.{key}")
                    return user_setting
            
            # Try tenant-specific setting
            if tenant_id:
                tenant_setting = self._get_tenant_setting(tenant_id, category, key)
                if tenant_setting is not None:
                    logger.debug(f"Found tenant setting for {category}.{key}")
                    return tenant_setting
            
            # Try global setting
            global_setting = self._get_global_setting(category, key)
            if global_setting is not None:
                logger.debug(f"Found global setting for {category}.{key}")
                return global_setting
            
            # Return default if nothing found
            logger.debug(f"Using default value for {category}.{key}")
            return default
            
        except Exception as e:
            logger.error(f"Error getting setting {category}.{key}: {e}")
            return default
    
    def set_global_default(self, 
                          category: str, 
                          key: str, 
                          value: Any, 
                          description: str = None,
                          is_overridable: bool = True) -> bool:
        """Set a global default setting"""
        try:
            # Check if setting already exists
            existing = self.db.query(GlobalDefault).filter(
                GlobalDefault.category == category,
                GlobalDefault.key == key
            ).first()
            
            if existing:
                existing.value = value
                existing.description = description
                existing.is_overridable = is_overridable
                existing.updated_at = datetime.utcnow()
            else:
                setting = GlobalDefault(
                    category=category,
                    key=key,
                    value=value,
                    description=description,
                    is_overridable=is_overridable
                )
                self.db.add(setting)
            
            self.db.commit()
            self._clear_cache(category, key)
            
            logger.info(f"Set global default: {category}.{key}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting global default {category}.{key}: {e}")
            self.db.rollback()
            return False
    
    def set_tenant_default(self, 
                          tenant_id: str,
                          category: str, 
                          key: str, 
                          value: Any,
                          inherit_from_global: bool = True) -> bool:
        """Set a tenant-specific default setting"""
        try:
            # Check if setting already exists
            existing = self.db.query(TenantDefault).filter(
                TenantDefault.tenant_id == tenant_id,
                TenantDefault.category == category,
                TenantDefault.key == key
            ).first()
            
            if existing:
                existing.value = value
                existing.inherits_from_global = inherit_from_global
                existing.updated_at = datetime.utcnow()
            else:
                setting = TenantDefault(
                    tenant_id=tenant_id,
                    category=category,
                    key=key,
                    value=value,
                    inherits_from_global=inherit_from_global
                )
                self.db.add(setting)
            
            self.db.commit()
            self._clear_cache(category, key, tenant_id=tenant_id)
            
            logger.info(f"Set tenant default: {category}.{key} for tenant {tenant_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting tenant default {category}.{key}: {e}")
            self.db.rollback()
            return False
    
    def set_user_default(self, 
                        user_id: str,
                        category: str, 
                        key: str, 
                        value: Any,
                        inherit_from_tenant: bool = True) -> bool:
        """Set a user-specific default setting"""
        try:
            # Check if setting already exists
            existing = self.db.query(UserDefault).filter(
                UserDefault.user_id == user_id,
                UserDefault.category == category,
                UserDefault.key == key
            ).first()
            
            if existing:
                existing.value = value
                existing.inherits_from_tenant = inherit_from_tenant
                existing.updated_at = datetime.utcnow()
            else:
                setting = UserDefault(
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    inherits_from_tenant=inherit_from_tenant
                )
                self.db.add(setting)
            
            self.db.commit()
            self._clear_cache(category, key, user_id=user_id)
            
            logger.info(f"Set user default: {category}.{key} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting user default {category}.{key}: {e}")
            self.db.rollback()
            return False
    
    def get_effective_settings(self, 
                              user_id: str = None, 
                              tenant_id: str = None,
                              categories: List[str] = None) -> Dict[str, Any]:
        """Get all effective settings for a user/tenant with inheritance applied"""
        try:
            settings = {}
            
            # Get all categories if not specified
            if not categories:
                categories = self._get_all_categories()
            
            for category in categories:
                settings[category] = {}
                
                # Get all keys for this category
                category_keys = self._get_category_keys(category, user_id, tenant_id)
                
                for key in category_keys:
                    value = self.get_setting(key, category, user_id, tenant_id)
                    if value is not None:
                        settings[category][key] = value
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting effective settings: {e}")
            return {}
    
    def cascade_global_updates(self, 
                              category: str, 
                              key: str, 
                              value: Any) -> List[str]:
        """
        Update global default and cascade to tenants/users that inherit
        Returns list of affected entities
        """
        try:
            affected = []
            
            # Update global default
            if self.set_global_default(category, key, value):
                affected.append("global")
            
            # Find tenants that inherit this setting
            inheriting_tenants = self.db.query(TenantDefault).filter(
                TenantDefault.category == category,
                TenantDefault.key == key,
                TenantDefault.inherits_from_global == True
            ).all()
            
            # Find users that inherit from tenant (and tenant inherits from global)
            for tenant_default in inheriting_tenants:
                inheriting_users = self.db.query(UserDefault).filter(
                    UserDefault.category == category,
                    UserDefault.key == key,
                    UserDefault.inherits_from_tenant == True
                ).all()
                
                for user_default in inheriting_users:
                    affected.append(f"user:{user_default.user_id}")
                
                affected.append(f"tenant:{tenant_default.tenant_id}")
            
            # Clear cache for affected entities
            self._clear_cache(category, key)
            
            logger.info(f"Cascaded update for {category}.{key} to {len(affected)} entities")
            return affected
            
        except Exception as e:
            logger.error(f"Error cascading updates for {category}.{key}: {e}")
            return []
    
    def load_defaults_from_config(self) -> Dict[str, int]:
        """Load defaults from YAML configuration files"""
        try:
            results = {
                "global": 0,
                "tenant": 0,
                "user": 0,
                "errors": 0
            }
            
            # Load global defaults
            global_path = Path(self.config_path) / "global"
            if global_path.exists():
                for config_file in global_path.glob("*.yaml"):
                    try:
                        category = config_file.stem
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        count = self._load_category_config(category, config_data, "global")
                        results["global"] += count
                        
                    except Exception as e:
                        logger.error(f"Error loading global config {config_file}: {e}")
                        results["errors"] += 1
            
            # Load tenant defaults
            tenant_path = Path(self.config_path) / "tenant"
            if tenant_path.exists():
                for config_file in tenant_path.glob("*.yaml"):
                    try:
                        category = config_file.stem.replace("_defaults", "")
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        count = self._load_category_config(category, config_data, "tenant_template")
                        results["tenant"] += count
                        
                    except Exception as e:
                        logger.error(f"Error loading tenant config {config_file}: {e}")
                        results["errors"] += 1
            
            # Load user defaults
            user_path = Path(self.config_path) / "user"
            if user_path.exists():
                for config_file in user_path.glob("*.yaml"):
                    try:
                        category = config_file.stem
                        with open(config_file, 'r') as f:
                            config_data = yaml.safe_load(f)
                        
                        count = self._load_category_config(category, config_data, "user_template")
                        results["user"] += count
                        
                    except Exception as e:
                        logger.error(f"Error loading user config {config_file}: {e}")
                        results["errors"] += 1
            
            logger.info(f"Loaded defaults from config: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error loading defaults from config: {e}")
            return {"global": 0, "tenant": 0, "user": 0, "errors": 1}
    
    # Private helper methods
    
    def _get_user_setting(self, user_id: str, category: str, key: str) -> Any:
        """Get user-specific setting"""
        setting = self.db.query(UserDefault).filter(
            UserDefault.user_id == user_id,
            UserDefault.category == category,
            UserDefault.key == key
        ).first()
        
        return setting.value if setting else None
    
    def _get_tenant_setting(self, tenant_id: str, category: str, key: str) -> Any:
        """Get tenant-specific setting"""
        setting = self.db.query(TenantDefault).filter(
            TenantDefault.tenant_id == tenant_id,
            TenantDefault.category == category,
            TenantDefault.key == key
        ).first()
        
        return setting.value if setting else None
    
    def _get_global_setting(self, category: str, key: str) -> Any:
        """Get global setting"""
        setting = self.db.query(GlobalDefault).filter(
            GlobalDefault.category == category,
            GlobalDefault.key == key
        ).first()
        
        return setting.value if setting else None
    
    def _load_category_config(self, category: str, config_data: Dict, level: str) -> int:
        """Load configuration data for a category"""
        count = 0
        
        def _process_nested(data: Dict, prefix: str = ""):
            nonlocal count
            for key, value in data.items():
                full_key = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict) and not self._is_leaf_dict(value):
                    # Recursively process nested dictionaries
                    _process_nested(value, full_key)
                else:
                    # This is a leaf value, store it
                    if level == "global":
                        self.set_global_default(category, full_key, value)
                    count += 1
        
        _process_nested(config_data)
        return count
    
    def _is_leaf_dict(self, data: Any) -> bool:
        """Check if a dictionary is a leaf node (contains only primitive values)"""
        if not isinstance(data, dict):
            return True
        
        return all(not isinstance(v, dict) for v in data.values())
    
    def _get_all_categories(self) -> List[str]:
        """Get all available categories"""
        categories = set()
        
        # From global defaults
        global_categories = self.db.query(GlobalDefault.category).distinct().all()
        categories.update(cat[0] for cat in global_categories)
        
        # From tenant defaults
        tenant_categories = self.db.query(TenantDefault.category).distinct().all()
        categories.update(cat[0] for cat in tenant_categories)
        
        # From user defaults
        user_categories = self.db.query(UserDefault.category).distinct().all()
        categories.update(cat[0] for cat in user_categories)
        
        return list(categories)
    
    def _get_category_keys(self, category: str, user_id: str = None, tenant_id: str = None) -> List[str]:
        """Get all keys for a category across all levels"""
        keys = set()
        
        # Global keys
        global_keys = self.db.query(GlobalDefault.key).filter(
            GlobalDefault.category == category
        ).all()
        keys.update(key[0] for key in global_keys)
        
        # Tenant keys
        if tenant_id:
            tenant_keys = self.db.query(TenantDefault.key).filter(
                TenantDefault.tenant_id == tenant_id,
                TenantDefault.category == category
            ).all()
            keys.update(key[0] for key in tenant_keys)
        
        # User keys
        if user_id:
            user_keys = self.db.query(UserDefault.key).filter(
                UserDefault.user_id == user_id,
                UserDefault.category == category
            ).all()
            keys.update(key[0] for key in user_keys)
        
        return list(keys)
    
    def _clear_cache(self, category: str, key: str, user_id: str = None, tenant_id: str = None):
        """Clear cached values for the given setting"""
        # Clear specific cache entries
        cache_keys_to_remove = []
        for cache_key in self._cache.keys():
            if cache_key.startswith(f"{category}.{key}"):
                cache_keys_to_remove.append(cache_key)
        
        for cache_key in cache_keys_to_remove:
            del self._cache[cache_key]


# Factory function for easy access
def get_defaults_manager(db_session: Session, config_path: str = None) -> DefaultsManager:
    """Factory function to create a DefaultsManager instance"""
    return DefaultsManager(db_session, config_path)
