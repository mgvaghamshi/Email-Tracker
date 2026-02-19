"""
Contact Management API Endpoints
Handles all contact-related operations including CRUD, bulk operations, and contact statistics
"""
from fastapi import APIRouter, HTTPException, Depends, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr, Field
import uuid
import logging
import csv
import io

from ...db import SessionLocal
from ...auth.jwt_auth import get_current_user
from ...database.user_models import User

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============= Pydantic Schemas =============

class ContactCreate(BaseModel):
    """Schema for creating a new contact"""
    email: EmailStr = Field(..., description="Contact email address")
    first_name: Optional[str] = Field(None, description="Contact first name")
    last_name: Optional[str] = Field(None, description="Contact last name")
    status: str = Field(default="active", pattern="^(active|unsubscribed|bounced)$", description="Contact status")
    tags: Optional[List[str]] = Field(None, description="List of tags for categorization")
    custom_fields: Optional[Dict[str, Any]] = Field(None, description="Dictionary of custom fields")


class ContactUpdate(BaseModel):
    """Schema for updating an existing contact"""
    email: Optional[EmailStr] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|unsubscribed|bounced)$")
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class ContactResponse(BaseModel):
    """Schema for contact response"""
    id: str
    user_id: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    status: str = "active"
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    last_activity: Optional[datetime] = None

    class Config:
        from_attributes = True


class ContactList(BaseModel):
    """Schema for paginated contact list response"""
    data: List[ContactResponse]
    total: int
    page: int
    limit: int
    pages: int


class ContactStats(BaseModel):
    """Schema for contact statistics"""
    total_contacts: int
    active_contacts: int
    unsubscribed_contacts: int
    bounced_contacts: int
    recent_contacts_count: int


class BulkDeleteRequest(BaseModel):
    """Schema for bulk delete request"""
    ids: List[str] = Field(..., description="List of contact IDs to delete")


# ============= Mock Contact Model (In-Memory Storage) =============
# Since Contact model doesn't exist in models.py, we'll use in-memory storage
# In production, this should be replaced with a proper database model

class ContactStore:
    """In-memory contact storage (temporary solution)"""
    contacts: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def create(cls, contact_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new contact"""
        contact_id = str(uuid.uuid4())
        contact = {
            "id": contact_id,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            **contact_data
        }
        cls.contacts[contact_id] = contact
        return contact
    
    @classmethod
    def get(cls, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a contact by ID"""
        return cls.contacts.get(contact_id)
    
    @classmethod
    def get_by_user(cls, user_id: str, skip: int = 0, limit: int = 50, 
                    status: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get contacts by user with filtering"""
        user_contacts = [c for c in cls.contacts.values() if c.get("user_id") == user_id]
        
        # Apply status filter
        if status:
            user_contacts = [c for c in user_contacts if c.get("status") == status]
        
        # Apply search filter
        if search:
            search_lower = search.lower()
            user_contacts = [
                c for c in user_contacts 
                if (search_lower in c.get("email", "").lower() or
                    search_lower in c.get("first_name", "").lower() or
                    search_lower in c.get("last_name", "").lower())
            ]
        
        # Sort by created_at desc
        user_contacts.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)
        
        return user_contacts[skip:skip + limit]
    
    @classmethod
    def count_by_user(cls, user_id: str, status: Optional[str] = None, search: Optional[str] = None) -> int:
        """Count contacts by user with filtering"""
        user_contacts = [c for c in cls.contacts.values() if c.get("user_id") == user_id]
        
        if status:
            user_contacts = [c for c in user_contacts if c.get("status") == status]
        
        if search:
            search_lower = search.lower()
            user_contacts = [
                c for c in user_contacts 
                if (search_lower in c.get("email", "").lower() or
                    search_lower in c.get("first_name", "").lower() or
                    search_lower in c.get("last_name", "").lower())
            ]
        
        return len(user_contacts)
    
    @classmethod
    def update(cls, contact_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a contact"""
        if contact_id not in cls.contacts:
            return None
        
        cls.contacts[contact_id].update(update_data)
        cls.contacts[contact_id]["updated_at"] = datetime.utcnow()
        return cls.contacts[contact_id]
    
    @classmethod
    def delete(cls, contact_id: str) -> bool:
        """Delete a contact"""
        if contact_id in cls.contacts:
            del cls.contacts[contact_id]
            return True
        return False
    
    @classmethod
    def bulk_delete(cls, contact_ids: List[str]) -> int:
        """Bulk delete contacts"""
        deleted_count = 0
        for contact_id in contact_ids:
            if cls.delete(contact_id):
                deleted_count += 1
        return deleted_count


# ============= API Endpoints =============

@router.get("/", response_model=ContactList)
async def list_contacts(
    skip: int = Query(0, ge=0, description="Number of contacts to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of contacts to return"),
    status: Optional[str] = Query(None, description="Filter by contact status"),
    search: Optional[str] = Query(None, description="Search by email, first name, or last name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a paginated list of contacts for the authenticated user.
    
    - **skip**: Number of contacts to skip (for pagination)
    - **limit**: Maximum number of contacts to return (1-100)
    - **status**: Optional status filter (active, unsubscribed, bounced)
    - **search**: Optional search term for email, first name, or last name
    """
    try:
        # Get contacts from store
        contacts = ContactStore.get_by_user(
            user_id=current_user.id,
            skip=skip,
            limit=limit,
            status=status,
            search=search
        )
        
        # Get total count
        total = ContactStore.count_by_user(
            user_id=current_user.id,
            status=status,
            search=search
        )
        
        # Calculate pagination
        page = (skip // limit) + 1
        pages = (total + limit - 1) // limit
        
        # Convert to response models
        contact_responses = [ContactResponse(**contact) for contact in contacts]
        
        return ContactList(
            data=contact_responses,
            total=total,
            page=page,
            limit=limit,
            pages=pages
        )
        
    except Exception as e:
        logger.error(f"Error listing contacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing contacts: {str(e)}"
        )


@router.post("/", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new contact for the authenticated user.
    
    - **email**: Contact email address (required, must be unique per user)
    - **first_name**: Contact first name (optional)
    - **last_name**: Contact last name (optional)
    - **status**: Contact status (active, unsubscribed, bounced)
    - **tags**: List of tags for categorization (optional)
    - **custom_fields**: Dictionary of custom fields (optional)
    """
    try:
        # Check if email already exists for this user
        existing_contacts = ContactStore.get_by_user(current_user.id)
        if any(c.get("email") == contact_data.email for c in existing_contacts):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contact with this email already exists"
            )
        
        # Create contact
        contact = ContactStore.create({
            "user_id": current_user.id,
            "email": contact_data.email,
            "first_name": contact_data.first_name,
            "last_name": contact_data.last_name,
            "status": contact_data.status,
            "tags": contact_data.tags,
            "custom_fields": contact_data.custom_fields,
            "last_activity": None
        })
        
        return ContactResponse(**contact)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating contact: {str(e)}"
        )


@router.get("/stats/overview", response_model=ContactStats)
async def get_contact_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get overview statistics for contacts.
    
    Returns counts by status and recent activity.
    """
    try:
        # Get all user contacts
        all_contacts = ContactStore.get_by_user(current_user.id, skip=0, limit=10000)
        
        total_contacts = len(all_contacts)
        active_contacts = len([c for c in all_contacts if c.get("status") == "active"])
        unsubscribed_contacts = len([c for c in all_contacts if c.get("status") == "unsubscribed"])
        bounced_contacts = len([c for c in all_contacts if c.get("status") == "bounced"])
        
        # Recent contacts (last 7 days)
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        recent_contacts_count = len([
            c for c in all_contacts 
            if c.get("created_at", datetime.min) > seven_days_ago
        ])
        
        return ContactStats(
            total_contacts=total_contacts,
            active_contacts=active_contacts,
            unsubscribed_contacts=unsubscribed_contacts,
            bounced_contacts=bounced_contacts,
            recent_contacts_count=recent_contacts_count
        )
        
    except Exception as e:
        logger.error(f"Error getting contact stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting contact stats: {str(e)}"
        )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve a specific contact by ID.
    
    - **contact_id**: Unique identifier for the contact
    """
    try:
        contact = ContactStore.get(contact_id)
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        # Verify ownership
        if contact.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this contact"
            )
        
        return ContactResponse(**contact)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting contact: {str(e)}"
        )


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    contact_data: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing contact.
    
    - **contact_id**: Unique identifier for the contact
    - All other fields are optional and will only be updated if provided
    """
    try:
        contact = ContactStore.get(contact_id)
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        # Verify ownership
        if contact.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this contact"
            )
        
        # Update contact
        update_data = contact_data.dict(exclude_unset=True)
        updated_contact = ContactStore.update(contact_id, update_data)
        
        return ContactResponse(**updated_contact)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating contact: {str(e)}"
        )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a contact by ID.
    
    - **contact_id**: Unique identifier for the contact
    """
    try:
        contact = ContactStore.get(contact_id)
        
        if not contact:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contact not found"
            )
        
        # Verify ownership
        if contact.get("user_id") != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this contact"
            )
        
        ContactStore.delete(contact_id)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting contact: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting contact: {str(e)}"
        )


@router.delete("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_contacts(
    contact_ids: Dict[str, List[str]],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete multiple contacts at once.
    
    - **contact_ids**: Dictionary containing list of contact IDs to delete
    
    Example request body:
    ```json
    {
        "ids": ["contact-id-1", "contact-id-2", "contact-id-3"]
    }
    ```
    """
    try:
        ids_to_delete = contact_ids.get("ids", [])
        
        if not ids_to_delete:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No contact IDs provided"
            )
        
        # Verify ownership and delete
        deleted_count = 0
        failed_ids = []
        
        for contact_id in ids_to_delete:
            contact = ContactStore.get(contact_id)
            
            if not contact:
                failed_ids.append({"id": contact_id, "reason": "not found"})
                continue
            
            if contact.get("user_id") != current_user.id:
                failed_ids.append({"id": contact_id, "reason": "not authorized"})
                continue
            
            if ContactStore.delete(contact_id):
                deleted_count += 1
        
        return {
            "deleted": deleted_count,
            "failed": len(failed_ids),
            "failed_ids": failed_ids,
            "message": f"Successfully deleted {deleted_count} contacts"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk deleting contacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error bulk deleting contacts: {str(e)}"
        )


@router.post("/bulk-upload")
async def bulk_upload_contacts(
    file: UploadFile = File(..., description="CSV file with contact data"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload contacts in bulk from a CSV file.
    
    CSV should have columns: email (required), first_name, last_name, status, tags
    """
    try:
        # Read CSV file
        contents = await file.read()
        csv_data = contents.decode('utf-8')
        csv_reader = csv.DictReader(io.StringIO(csv_data))
        
        created_count = 0
        failed_count = 0
        errors = []
        
        for row in csv_reader:
            try:
                email = row.get('email', '').strip()
                
                if not email:
                    failed_count += 1
                    errors.append({"row": row, "error": "Missing email"})
                    continue
                
                # Check if email already exists
                existing_contacts = ContactStore.get_by_user(current_user.id)
                if any(c.get("email") == email for c in existing_contacts):
                    failed_count += 1
                    errors.append({"row": row, "error": "Email already exists"})
                    continue
                
                # Parse tags
                tags = None
                if 'tags' in row and row['tags']:
                    tags = [tag.strip() for tag in row['tags'].split(',')]
                
                # Create contact
                ContactStore.create({
                    "user_id": current_user.id,
                    "email": email,
                    "first_name": row.get('first_name', '').strip() or None,
                    "last_name": row.get('last_name', '').strip() or None,
                    "status": row.get('status', 'active').strip(),
                    "tags": tags,
                    "custom_fields": {},
                    "last_activity": None
                })
                
                created_count += 1
                
            except Exception as e:
                failed_count += 1
                errors.append({"row": row, "error": str(e)})
        
        return {
            "created": created_count,
            "failed": failed_count,
            "errors": errors[:10],  # Return first 10 errors
            "message": f"Successfully uploaded {created_count} contacts"
        }
        
    except Exception as e:
        logger.error(f"Error bulk uploading contacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error bulk uploading contacts: {str(e)}"
        )


@router.get("/export/csv")
async def export_contacts_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export all contacts to a CSV file.
    """
    try:
        # Get all user contacts
        contacts = ContactStore.get_by_user(current_user.id, skip=0, limit=100000)
        
        # Create CSV in memory
        output = io.StringIO()
        fieldnames = ['id', 'email', 'first_name', 'last_name', 'status', 'tags', 'created_at', 'updated_at']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        for contact in contacts:
            # Convert tags list to comma-separated string
            tags_str = ','.join(contact.get('tags', [])) if contact.get('tags') else ''
            
            writer.writerow({
                'id': contact.get('id'),
                'email': contact.get('email'),
                'first_name': contact.get('first_name', ''),
                'last_name': contact.get('last_name', ''),
                'status': contact.get('status', 'active'),
                'tags': tags_str,
                'created_at': contact.get('created_at', ''),
                'updated_at': contact.get('updated_at', '')
            })
        
        # Prepare response
        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=contacts_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting contacts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting contacts: {str(e)}"
        )
