"""
Create default roles in the database
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import SessionLocal
from app.database.user_models import Role
import uuid
import json

def create_default_roles():
    """Create default User and Admin roles"""
    db = SessionLocal()
    try:
        # Check if roles already exist
        existing_roles = db.query(Role).count()
        if existing_roles > 0:
            print(f"✓ Roles already exist ({existing_roles} roles found)")
            return
        
        # Create User role (default)
        user_role = Role(
            id=str(uuid.uuid4()),
            name="User",
            description="Default user role with basic permissions",
            is_default=True,
            is_system=True,
            permissions=json.dumps({
                "campaigns": ["read", "create", "update", "delete_own"],
                "templates": ["read", "create", "update", "delete_own"],
                "analytics": ["read_own"],
                "profile": ["read", "update"]
            })
        )
        db.add(user_role)
        
        # Create Admin role
        admin_role = Role(
            id=str(uuid.uuid4()),
            name="Admin",
            description="Administrator role with full permissions",
            is_default=False,
            is_system=True,
            permissions=json.dumps({
                "campaigns": ["read", "create", "update", "delete", "manage_all"],
                "templates": ["read", "create", "update", "delete", "manage_all"],
                "analytics": ["read", "read_all"],
                "users": ["read", "create", "update", "delete", "manage_roles"],
                "settings": ["read", "update", "manage_system"],
                "profile": ["read", "update"]
            })
        )
        db.add(admin_role)
        
        db.commit()
        print("✓ Successfully created default roles:")
        print(f"  - User role (default): {user_role.id}")
        print(f"  - Admin role: {admin_role.id}")
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error creating roles: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_default_roles()
