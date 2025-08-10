"""
Contact management endpoints with user-based data isolation
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_
from typing import List, Optional
import uuid
import json
import csv
import io
import logging
from datetime import datetime, timedelta

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.models import Contact, EmailTracker
from ...database.user_models import User
from ...schemas.contacts import ContactCreate, ContactUpdate, ContactResponse, ContactList, ContactStats

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("/", summary="List all contacts", response_model=ContactList)
async def list_contacts(
    skip: int = Query(0, ge=0, description="Number of contacts to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of contacts to return"),
    status: Optional[str] = Query(None, description="Filter by contact status"),
    search: Optional[str] = Query(None, description="Search by email, first name, or last name"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Retrieve a paginated list of contacts for the authenticated user.
    
    - **skip**: Number of contacts to skip (for pagination)
    - **limit**: Maximum number of contacts to return (1-100)
    - **status**: Optional status filter (active, unsubscribed, bounced)
    - **search**: Optional search term for email, first name, or last name
    """
    query = db.query(Contact).filter(Contact.user_id == current_user.id)
    
    if status:
        query = query.filter(Contact.status == status)
    
    if search:
        search_filter = or_(
            Contact.email.ilike(f"%{search}%"),
            Contact.first_name.ilike(f"%{search}%"),
            Contact.last_name.ilike(f"%{search}%")
        )
        query = query.filter(search_filter)
    
    total = query.count()
    contacts = query.offset(skip).limit(limit).all()
    
    # Calculate pagination
    page = (skip // limit) + 1
    pages = (total + limit - 1) // limit
    
    # Convert to response format
    contact_responses = []
    for contact in contacts:
        contact_dict = {
            "id": contact.id,
            "user_id": contact.user_id,
            "email": contact.email,
            "first_name": contact.first_name,
            "last_name": contact.last_name,
            "status": contact.status,
            "tags": json.loads(contact.tags) if contact.tags else [],
            "custom_fields": json.loads(contact.custom_fields) if contact.custom_fields else {},
            "created_at": contact.created_at,
            "updated_at": contact.updated_at
        }
        contact_responses.append(ContactResponse(**contact_dict))
    
    return ContactList(
        data=contact_responses,
        total=total,
        page=page,
        limit=limit,
        pages=pages
    )


@router.post("/", summary="Create a new contact", response_model=ContactResponse)
async def create_contact(
    contact_data: ContactCreate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
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
    # Check if contact already exists for this user
    existing_contact = db.query(Contact).filter(
        and_(
            Contact.user_id == current_user.id,
            Contact.email == contact_data.email
        )
    ).first()
    
    if existing_contact:
        raise HTTPException(
            status_code=400, 
            detail=f"Contact with email {contact_data.email} already exists"
        )
    
    # Create new contact
    contact = Contact(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        email=contact_data.email,
        first_name=contact_data.first_name,
        last_name=contact_data.last_name,
        status=contact_data.status,
        tags=json.dumps(contact_data.tags) if contact_data.tags else None,
        custom_fields=json.dumps(contact_data.custom_fields) if contact_data.custom_fields else None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    db.add(contact)
    db.commit()
    db.refresh(contact)
    
    # Convert to response format
    contact_dict = {
        "id": contact.id,
        "user_id": contact.user_id,
        "email": contact.email,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "status": contact.status,
        "tags": json.loads(contact.tags) if contact.tags else [],
        "custom_fields": json.loads(contact.custom_fields) if contact.custom_fields else {},
        "created_at": contact.created_at,
        "updated_at": contact.updated_at
    }
    
    return ContactResponse(**contact_dict)


@router.delete("/bulk-delete", summary="Bulk delete contacts")
async def bulk_delete_contacts(
    contact_ids: dict,  # Expected format: {"ids": ["id1", "id2", ...]}
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
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
    ids = contact_ids.get("ids", [])
    if not ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No contact IDs provided"
        )
    
    if len(ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete more than 100 contacts at once"
        )
    
    # Validate that all IDs are strings
    if not all(isinstance(id_val, str) for id_val in ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="All contact IDs must be strings"
        )
    
    try:
        # Delete contacts that belong to this user
        deleted_count = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.id.in_(ids)
            )
        ).delete(synchronize_session=False)
        
        db.commit()
        
        if deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No contacts found to delete. Make sure the contact IDs belong to your account."
            )
        
        return {
            "message": f"Successfully deleted {deleted_count} contacts",
            "deleted_count": deleted_count,
            "requested_count": len(ids)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during bulk delete: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while deleting contacts"
        )


@router.get("/{contact_id}", summary="Get contact by ID", response_model=ContactResponse)
async def get_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific contact by ID.
    
    - **contact_id**: Unique identifier for the contact
    """
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    contact_dict = {
        "id": contact.id,
        "user_id": contact.user_id,
        "email": contact.email,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "status": contact.status,
        "tags": json.loads(contact.tags) if contact.tags else [],
        "custom_fields": json.loads(contact.custom_fields) if contact.custom_fields else {},
        "created_at": contact.created_at,
        "updated_at": contact.updated_at
    }
    
    return ContactResponse(**contact_dict)


@router.put("/{contact_id}", summary="Update contact", response_model=ContactResponse)
async def update_contact(
    contact_id: str,
    contact_data: ContactUpdate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Update an existing contact.
    
    - **contact_id**: Unique identifier for the contact
    - All other fields are optional and will only be updated if provided
    """
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    # Update fields if provided
    if contact_data.email is not None:
        # Check if email is already taken by another contact
        existing_contact = db.query(Contact).filter(
            and_(
                Contact.user_id == current_user.id,
                Contact.email == contact_data.email,
                Contact.id != contact_id
            )
        ).first()
        
        if existing_contact:
            raise HTTPException(
                status_code=400,
                detail=f"Email {contact_data.email} is already used by another contact"
            )
        
        contact.email = contact_data.email
    
    if contact_data.first_name is not None:
        contact.first_name = contact_data.first_name
    
    if contact_data.last_name is not None:
        contact.last_name = contact_data.last_name
    
    if contact_data.status is not None:
        contact.status = contact_data.status
    
    if contact_data.tags is not None:
        contact.tags = json.dumps(contact_data.tags)
    
    if contact_data.custom_fields is not None:
        contact.custom_fields = json.dumps(contact_data.custom_fields)
    
    contact.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(contact)
    
    contact_dict = {
        "id": contact.id,
        "user_id": contact.user_id,
        "email": contact.email,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "status": contact.status,
        "tags": json.loads(contact.tags) if contact.tags else [],
        "custom_fields": json.loads(contact.custom_fields) if contact.custom_fields else {},
        "created_at": contact.created_at,
        "updated_at": contact.updated_at
    }
    
    return ContactResponse(**contact_dict)


@router.delete("/{contact_id}", summary="Delete contact")
async def delete_contact(
    contact_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Delete a contact by ID.
    
    - **contact_id**: Unique identifier for the contact
    """
    contact = db.query(Contact).filter(
        and_(
            Contact.id == contact_id,
            Contact.user_id == current_user.id
        )
    ).first()
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    db.delete(contact)
    db.commit()
    
    return {"message": "Contact deleted successfully"}


@router.get("/stats/overview", summary="Get contact statistics", response_model=ContactStats)
async def get_contact_stats(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get overview statistics for contacts.
    
    Returns counts by status and recent activity.
    """
    # Get contact counts by status
    stats = db.query(
        Contact.status,
        func.count(Contact.id).label('count')
    ).filter(Contact.user_id == current_user.id).group_by(Contact.status).all()
    
    status_counts = {stat.status: stat.count for stat in stats}
    
    # Get total count
    total_contacts = db.query(func.count(Contact.id)).filter(Contact.user_id == current_user.id).scalar()
    
    # Get recent activity (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    recent_contacts = db.query(func.count(Contact.id)).filter(
        and_(
            Contact.user_id == current_user.id,
            Contact.created_at >= thirty_days_ago
        )
    ).scalar()
    
    return ContactStats(
        total_contacts=total_contacts,
        active_contacts=status_counts.get('active', 0),
        unsubscribed_contacts=status_counts.get('unsubscribed', 0),
        bounced_contacts=status_counts.get('bounced', 0),
        recent_contacts=recent_contacts
    )


@router.post("/bulk-upload", summary="Bulk upload contacts from CSV")
async def bulk_upload_contacts(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Upload contacts in bulk from a CSV file.
    
    CSV should have columns: email (required), first_name, last_name, status, tags
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    csv_data = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_data))
    
    created_count = 0
    skipped_count = 0
    errors = []
    
    for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because row 1 is headers
        try:
            email = row.get('email', '').strip()
            if not email:
                errors.append(f"Row {row_num}: Email is required")
                continue
            
            # Check if contact already exists
            existing_contact = db.query(Contact).filter(
                and_(
                    Contact.user_id == current_user.id,
                    Contact.email == email
                )
            ).first()
            
            if existing_contact:
                skipped_count += 1
                continue
            
            # Create contact
            contact = Contact(
                id=str(uuid.uuid4()),
                user_id=current_user.id,
                email=email,
                first_name=row.get('first_name', '').strip() or None,
                last_name=row.get('last_name', '').strip() or None,
                status=row.get('status', 'active').strip(),
                tags=json.dumps(row.get('tags', '').split(',')) if row.get('tags') else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.add(contact)
            created_count += 1
            
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save contacts: {str(e)}")
    
    return {
        "message": f"Bulk upload completed",
        "created": created_count,
        "skipped": skipped_count,
        "errors": errors
    }


@router.get("/export/csv", summary="Export contacts to CSV")
async def export_contacts_csv(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Export all contacts to a CSV file.
    """
    contacts = db.query(Contact).filter(Contact.user_id == current_user.id).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['id', 'email', 'first_name', 'last_name', 'status', 'tags', 'created_at', 'updated_at'])
    
    # Write data
    for contact in contacts:
        tags = json.loads(contact.tags) if contact.tags else []
        writer.writerow([
            contact.id,
            contact.email,
            contact.first_name or '',
            contact.last_name or '',
            contact.status,
            ','.join(tags),
            contact.created_at.isoformat() if contact.created_at else '',
            contact.updated_at.isoformat() if contact.updated_at else ''
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"}
    )
