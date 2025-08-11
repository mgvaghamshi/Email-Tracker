"""
Campaign management endpoints with user-based data isolation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import List, Optional, Dict, Any
import uuid
import re
from datetime import datetime, timezone

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.models import Campaign, EmailTracker, CampaignRecipient, Contact, Template, EmailBounce
from ...database.api_key_models import ApiKey
from ...database.user_models import User
from ...services.email_service import EmailService
from ...services.version_service import create_campaign_version
from ...schemas.email import EmailSendRequest
from ...schemas import campaigns as schemas
from ...database.user_models import ApiKey
from ...database.user_models import User

# Import settings functions
from .settings import load_setting

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/", summary="List all campaigns")
async def list_campaigns(
    skip: int = Query(0, ge=0, description="Number of campaigns to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of campaigns to return"),
    status: Optional[str] = Query(None, description="Filter by campaign status"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Retrieve a paginated list of campaigns for the authenticated user.
    
    - **skip**: Number of campaigns to skip (for pagination)
    - **limit**: Maximum number of campaigns to return (1-100)
    - **status**: Optional status filter (draft, scheduled, sending, completed, paused)
    """
    # Filter campaigns by the authenticated user
    query = db.query(Campaign).filter(Campaign.user_id == current_user.id)
    
    if status:
        query = query.filter(Campaign.status == status)
    
    total = query.count()
    campaigns = query.offset(skip).limit(limit).all()
    
    # Calculate stats for each campaign
    campaign_list = []
    for campaign in campaigns:
        # Get tracker statistics
        tracker_stats = db.query(
            func.count(EmailTracker.id).label('total'),
            func.sum(case((EmailTracker.delivered == True, 1), else_=0)).label('sent'),
            func.sum(EmailTracker.open_count).label('opens'),
            func.sum(EmailTracker.click_count).label('clicks')
        ).filter(EmailTracker.campaign_id == campaign.id).first()
        
        sent_count = tracker_stats.sent or 0
        open_count = tracker_stats.opens or 0
        click_count = tracker_stats.clicks or 0
        
        open_rate = (open_count / sent_count * 100) if sent_count > 0 else 0.0
        click_rate = (click_count / sent_count * 100) if sent_count > 0 else 0.0
        
        campaign_data = {
            "id": campaign.id,
            "name": campaign.name,
            "subject": campaign.subject,
            "description": campaign.description,
            "template_id": campaign.template_id,
            "status": campaign.status,
            "recipients_count": campaign.recipients_count,
            "sent_count": sent_count,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2),
            "created_at": campaign.created_at,
            "sent_at": campaign.sent_at
        }
        campaign_list.append(campaign_data)
    
    return {
        "data": campaign_list,
        "total": total,
        "page": (skip // limit) + 1,
        "limit": limit
    }


@router.post("/", summary="Create a new campaign")
async def create_campaign(
    campaign_data: dict,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create a new email campaign for the authenticated user.
    
    - **name**: Campaign name (required)
    - **subject**: Email subject line (required)
    - **description**: Optional campaign description
    """
    # Get user's active API key (or use None if JWT auth)
    api_key_obj = db.query(ApiKey).filter(
        ApiKey.user_id == current_user.id,
        ApiKey.is_active == True
    ).first()
    
    # Create new campaign
    campaign = Campaign(
        id=str(uuid.uuid4()),
        user_id=current_user.id,  # Ensure user ownership
        name=campaign_data.get("name"),
        subject=campaign_data.get("subject"),
        description=campaign_data.get("description"),
        template_id=campaign_data.get("templateId"),  # Store template association
        recipients_count=campaign_data.get("recipients_count", 0),  # Accept recipients count
        status="draft"
    )
    
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    
    # Add recipients if provided
    if campaign_data.get("metadata") and campaign_data["metadata"].get("selectedRecipients"):
        recipient_ids = campaign_data["metadata"]["selectedRecipients"]
        for contact_id in recipient_ids:
            # Verify contact belongs to user
            contact = db.query(Contact).filter(
                Contact.id == contact_id,
                Contact.user_id == current_user.id
            ).first()
            
            if contact:
                campaign_recipient = CampaignRecipient(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    user_id=current_user.id
                )
                db.add(campaign_recipient)
        
        db.commit()
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "subject": campaign.subject,
        "description": campaign.description,
        "template_id": campaign.template_id,
        "status": campaign.status,
        "recipients_count": campaign.recipients_count,  # Use actual recipients count
        "sent_count": 0,
        "open_rate": 0.0,
        "click_rate": 0.0,
        "created_at": campaign.created_at,
        "sent_at": campaign.sent_at
    }


@router.get("/{campaign_id}", summary="Get campaign details")
async def get_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific campaign including statistics.
    """
    # Get campaign owned by the authenticated user
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get detailed statistics
    tracker_stats = db.query(
        func.count(EmailTracker.id).label('total'),
        func.sum(case((EmailTracker.delivered == True, 1), else_=0)).label('delivered'),
        func.sum(case((EmailTracker.open_count > 0, 1), else_=0)).label('opened'),
        func.sum(case((EmailTracker.click_count > 0, 1), else_=0)).label('clicked'),
        func.sum(case((EmailTracker.bounced == True, 1), else_=0)).label('bounced'),
        func.sum(case((EmailTracker.unsubscribed == True, 1), else_=0)).label('unsubscribed')
    ).filter(EmailTracker.campaign_id == campaign_id).first()
    
    total_emails = tracker_stats.total or 0
    delivered = tracker_stats.delivered or 0
    opened = tracker_stats.opened or 0
    clicked = tracker_stats.clicked or 0
    bounced = tracker_stats.bounced or 0
    unsubscribed = tracker_stats.unsubscribed or 0
    
    # Calculate rates
    open_rate = (opened / delivered * 100) if delivered > 0 else 0.0
    click_rate = (clicked / delivered * 100) if delivered > 0 else 0.0
    bounce_rate = (bounced / total_emails * 100) if total_emails > 0 else 0.0
    unsubscribe_rate = (unsubscribed / delivered * 100) if delivered > 0 else 0.0
    
    # Get sample trackers
    sample_trackers = db.query(EmailTracker).filter(
        EmailTracker.campaign_id == campaign_id
    ).limit(10).all()
    
    campaign_data = {
        "id": campaign.id,
        "name": campaign.name,
        "subject": campaign.subject,
        "description": campaign.description,
        "status": campaign.status,
        "recipients_count": campaign.recipients_count,
        "sent_count": delivered,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "created_at": campaign.created_at,
        "sent_at": campaign.sent_at
    }
    
    stats = {
        "total_emails": total_emails,
        "delivered": delivered,
        "opened": opened,
        "clicked": clicked,
        "bounced": bounced,
        "unsubscribed": unsubscribed,
        "open_rate": round(open_rate, 2),
        "click_rate": round(click_rate, 2),
        "bounce_rate": round(bounce_rate, 2),
        "unsubscribe_rate": round(unsubscribe_rate, 2)
    }
    
    return {
        "campaign": campaign_data,
        "stats": stats,
        "trackers": [
            {
                "id": t.id,
                "recipient_email": t.recipient_email,
                "subject": t.subject,
                "delivered": t.delivered,
                "open_count": t.open_count,
                "click_count": t.click_count,
                "sent_at": t.sent_at,
                "opened_at": t.opened_at
            } for t in sample_trackers
        ]
    }


@router.put("/{campaign_id}", summary="Update campaign")
async def update_campaign(
    campaign_id: str,
    campaign_data: dict,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Update an existing campaign owned by the authenticated user.
    Can only update campaigns in draft status.
    """
    # Get campaign owned by the authenticated user
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Only allow updates for draft campaigns
    if campaign.status != "draft":
        raise HTTPException(
            status_code=400,
            detail="Can only update campaigns in draft status"
        )
    
    # Store old values for version tracking
    old_values = {
        "name": campaign.name,
        "subject": campaign.subject,
        "description": campaign.description,
        "template_id": campaign.template_id
    }
    
    # Track what changes are being made
    changes = []
    
    # Update basic fields
    if "name" in campaign_data and campaign_data["name"] != campaign.name:
        changes.append(f"Name changed from '{campaign.name}' to '{campaign_data['name']}'")
        campaign.name = campaign_data["name"]
    if "subject" in campaign_data and campaign_data["subject"] != campaign.subject:
        changes.append(f"Subject changed from '{campaign.subject}' to '{campaign_data['subject']}'")
        campaign.subject = campaign_data["subject"]
    if "description" in campaign_data and campaign_data["description"] != campaign.description:
        changes.append(f"Description updated")
        campaign.description = campaign_data["description"]
    if "template_id" in campaign_data and campaign_data["template_id"] != campaign.template_id:
        changes.append(f"Template changed")
        campaign.template_id = campaign_data["template_id"]
    
    # Update recipients if provided
    recipients_changed = False
    if "metadata" in campaign_data and campaign_data["metadata"].get("selectedRecipients"):
        # Get current recipients for comparison
        current_recipients = db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign.id
        ).all()
        current_recipient_ids = set(r.contact_id for r in current_recipients)
        new_recipient_ids = set(campaign_data["metadata"]["selectedRecipients"])
        
        if current_recipient_ids != new_recipient_ids:
            recipients_changed = True
            changes.append(f"Recipients updated ({len(new_recipient_ids)} recipients)")
            
            # Clear existing recipients
            db.query(CampaignRecipient).filter(
                CampaignRecipient.campaign_id == campaign.id
            ).delete()
            
            # Add new recipients
            recipients_count = 0
            for contact_id in campaign_data["metadata"]["selectedRecipients"]:
                # Verify contact belongs to user
                contact = db.query(Contact).filter(
                    Contact.id == contact_id,
                    Contact.user_id == current_user.id
                ).first()
                
                if contact:
                    campaign_recipient = CampaignRecipient(
                        campaign_id=campaign.id,
                        contact_id=contact.id,
                        user_id=current_user.id
                    )
                    db.add(campaign_recipient)
                    recipients_count += 1
            
            campaign.recipients_count = recipients_count
    
    # Create version if there were significant changes
    if changes:
        try:
            create_campaign_version(
                db=db,
                campaign=campaign,
                user=current_user,
                changes_summary="; ".join(changes)
            )
        except Exception as e:
            # Log the error but don't fail the update
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create campaign version: {str(e)}")
    
    campaign.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(campaign)
    
    return {
        "id": campaign.id,
        "name": campaign.name,
        "subject": campaign.subject,
        "description": campaign.description,
        "status": campaign.status,
        "recipients_count": campaign.recipients_count,
        "template_id": getattr(campaign, 'template_id', None),
        "sent_count": 0,  # Will be calculated from actual data
        "open_rate": 0.0,
        "click_rate": 0.0,
        "created_at": campaign.created_at,
        "sent_at": campaign.sent_at
    }


@router.delete("/{campaign_id}", summary="Delete campaign")
async def delete_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Delete a campaign owned by the authenticated user.
    
    Campaigns can be deleted in any status except 'sending' to prevent 
    interruption of active email delivery.
    """
    # Get campaign owned by the authenticated user
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Only prevent deletion if campaign is currently sending
    if campaign.status == "sending":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete campaign while it is currently being sent. Please wait for sending to complete."
        )
    
    # Delete campaign and all related data
    try:
        # Delete campaign recipients first (to avoid foreign key issues)
        db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == campaign_id
        ).delete()
        
        # Delete email trackers
        db.query(EmailTracker).filter(
            EmailTracker.campaign_id == campaign_id
        ).delete()
        
        # Delete the campaign itself
        db.delete(campaign)
        db.commit()
        
        return {
            "success": True,
            "message": "Campaign deleted successfully",
            "campaign_id": campaign_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete campaign: {str(e)}"
        )


@router.get("/{campaign_id}/preview", summary="Get campaign preview")
async def get_campaign_preview(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get a preview of the campaign email content using template if selected.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get template if specified
    template = None
    if campaign.template_id:
        template = db.query(Template).filter(
            Template.id == campaign.template_id,
            Template.user_id == current_user.id
        ).first()
    
    # Prepare email content for preview
    email_subject = campaign.subject
    
    # Use template content if available, otherwise use campaign description
    if template and template.html_content:
        # Use template content
        html_content = template.html_content
        text_content = template.text_content or ""
        
        # If template has subject, use it (unless campaign overrides)
        if template.subject and not email_subject:
            email_subject = template.subject
    else:
        # Fallback to campaign description or default content
        campaign_description = campaign.description or "Thank you for subscribing to our campaign."
        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{email_subject}</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .content {{ padding: 20px 0; }}
                .footer {{ border-top: 1px solid #eee; padding-top: 20px; margin-top: 20px; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{campaign.name}</h2>
            </div>
            <div class="content">
                <p>Hello [First Name],</p>
                <div>{campaign_description}</div>
                <p>Best regards,<br>The Team</p>
            </div>
            <div class="footer">
                <p>This email was sent as part of the "{campaign.name}" campaign.</p>
            </div>
        </body>
        </html>
        """
        text_content = f"""
        {campaign.name}
        
        Hello [First Name],
        
        {campaign_description}
        
        Best regards,
        The Team
        
        ---
        This email was sent as part of the "{campaign.name}" campaign.
        """
    
    return {
        "campaign_id": campaign.id,
        "subject": email_subject,
        "html_content": html_content,
        "text_content": text_content,
        "template_id": campaign.template_id,
        "template_name": template.name if template else None,
        "preview_note": "This is a preview showing how your email will look to recipients. [First Name] will be replaced with actual recipient names."
    }


@router.post("/{campaign_id}/send", summary="Send campaign")
async def send_campaign(
    campaign_id: str,
    send_data: dict = None,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Send a campaign to recipients using the selected template and campaign content.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    if campaign.status not in ["draft", "scheduled"]:
        raise HTTPException(
            status_code=400,
            detail="Campaign cannot be sent in current status"
        )
    
    # Get campaign recipients
    recipients = db.query(CampaignRecipient).join(Contact).filter(
        CampaignRecipient.campaign_id == campaign_id,
        CampaignRecipient.user_id == current_user.id,
        Contact.status == 'active'
    ).all()
    
    if not recipients:
        raise HTTPException(
            status_code=400,
            detail="Campaign has no recipients. Please add recipients before sending."
        )
    
    # Get template if specified
    template = None
    if campaign.template_id:
        template = db.query(Template).filter(
            Template.id == campaign.template_id,
            Template.user_id == current_user.id
        ).first()
    
    # Update campaign status
    campaign.status = "sending" 
    campaign.sent_at = datetime.now()
    db.commit()
    
    # Initialize email service
    email_service = EmailService()
    sent_count = 0
    failed_count = 0
    
    # Prepare email content
    email_subject = campaign.subject
    
    # Get user/company settings for personalization
    default_company = {
        "company_name": "Your Company",
        "company_website": "https://yourcompany.com",
        "company_logo": "",
        "company_address": "123 Business St, City, State 12345",
        "support_email": "support@yourcompany.com",
        "privacy_policy_url": "https://yourcompany.com/privacy",
        "terms_of_service_url": "https://yourcompany.com/terms"
    }
    
    # Load company settings from user preferences
    company_settings = load_setting("company", default_company, current_user.id)
    company_name = company_settings.get("company_name", "Your Company")
    company_email = company_settings.get("support_email", "noreply@yourdomain.com")
    company_website = company_settings.get("company_website", "https://yourcompany.com")
    company_address = company_settings.get("company_address", "123 Business St, City, State 12345")
    base_url = email_service.base_url
    
    # Use template content if available, with proper variable replacement
    if template and template.html_content:
        html_content_template = template.html_content
        text_content_template = template.text_content or ""
        
        # If template has subject, use it (unless campaign overrides)
        if template.subject and not email_subject:
            email_subject = template.subject
            
        # Replace template variables with campaign/user data
        template_variables = {
            '{{company_name}}': company_name,
            '{{campaign_name}}': campaign.name,
            '{{campaign_description}}': campaign.description or "",
            '{{unsubscribe_url}}': f"{base_url}/unsubscribe/{{tracker_id}}",
            '{{company_email}}': company_email,
            '{{company_website}}': company_website,
            '{{company_address}}': company_address,
            '{{year}}': str(datetime.now().year)
        }
        
        # Apply template variables to HTML content
        for variable, value in template_variables.items():
            html_content_template = html_content_template.replace(variable, value)
            text_content_template = text_content_template.replace(variable, value)
            
        # If campaign has description and template doesn't include it, add it
        if campaign.description and '{{campaign_description}}' not in template.html_content:
            # Insert campaign description after greeting
            greeting_pattern = r'(Hi\s+{{first_name}},?\s*<br>?\s*)'
            if re.search(greeting_pattern, html_content_template, re.IGNORECASE):
                html_content_template = re.sub(
                    greeting_pattern,
                    r'\1<div style="margin: 16px 0; padding: 16px; background-color: #f8f9fa; border-left: 4px solid #007bff; border-radius: 4px;">' + 
                    f'<strong>Campaign Message:</strong><br>{campaign.description}</div>',
                    html_content_template,
                    flags=re.IGNORECASE
                )
    else:
        # Fallback to campaign description with professional template
        campaign_description = campaign.description or "Thank you for subscribing to our campaign."
        html_content_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{email_subject}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px 20px; text-align: center; }}
        .content {{ padding: 30px 20px; }}
        .campaign-info {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #666; border-top: 1px solid #dee2e6; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .cta a {{ background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0; font-size: 28px;">{campaign.name}</h1>
        </div>
        <div class="content">
            <p style="font-size: 16px; margin-bottom: 20px;">Hello {{{{first_name}}}},</p>
            
            <div class="campaign-info">
                <h3 style="margin-top: 0; color: #007bff;">Campaign Message</h3>
                <div style="white-space: pre-line;">{campaign_description}</div>
            </div>
            
            <div class="cta">
                <a href="https://example.com/learn-more" style="background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">Learn More</a>
            </div>
            
            <p>Thank you for being part of our community. We appreciate your continued support.</p>
            
            <p style="margin-top: 30px;">
                Best regards,<br>
                The {{{{company_name}}}} Team
            </p>
        </div>
        <div class="footer">
            <p>© {{{{year}}}} {{{{company_name}}}}. All rights reserved.</p>
            <p>
                <a href="{{{{unsubscribe_url}}}}" style="color: #666;">Unsubscribe</a> from future emails.
            </p>
        </div>
    </div>
</body>
</html>"""
        
        text_content_template = f"""{campaign.name}

Hello {{{{first_name}}}},

Campaign Message:
{campaign_description}

Thank you for being part of our community. We appreciate your continued support.

Best regards,
The {{{{company_name}}}} Team

---
© {{{{year}}}} {{{{company_name}}}}. All rights reserved.
Unsubscribe: {{{{unsubscribe_url}}}}
"""
    
    # Send emails to all recipients
    for recipient in recipients:
        try:
            contact = recipient.contact
            
            # Create tracking ID
            tracker_id = str(uuid.uuid4())
            tracking_pixel_url = f"{email_service.base_url}/api/v1/track/open/{tracker_id}"
            
            # Personalize content with recipient-specific data
            first_name = contact.first_name or "there"
            
            # Create all personalization variables
            personalization_vars = {
                '{{first_name}}': first_name,
                '{{company_name}}': company_name,
                '{{campaign_name}}': campaign.name,
                '{{campaign_description}}': campaign.description or "",
                '{{unsubscribe_url}}': f"{base_url}/api/v1/unsubscribe/{tracker_id}",
                '{{company_email}}': company_email,
                '{{year}}': str(datetime.now().year),
                '{{tracker_id}}': tracker_id
            }
            
            # Apply all personalizations to both HTML and text
            personalized_html = html_content_template
            personalized_text = text_content_template
            
            for variable, value in personalization_vars.items():
                personalized_html = personalized_html.replace(variable, str(value))
                personalized_text = personalized_text.replace(variable, str(value))
            
            # Replace clickable links with tracked versions
            # This replaces href attributes with tracked URLs
            def replace_links(html_content):
                import re
                def track_link(match):
                    original_url = match.group(1)
                    if original_url.startswith('#') or 'unsubscribe' in original_url:
                        return f'href="{original_url}"'
                    # Create tracked URL
                    tracked_url = f"{base_url}/api/v1/track/click/{tracker_id}?url={original_url}"
                    return f'href="{tracked_url}"'
                
                return re.sub(r'href="([^"]*)"', track_link, html_content)
            
            personalized_html = replace_links(personalized_html)
            
            # Add tracking pixel to HTML content
            tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" alt="" />'
            if "</body>" in personalized_html:
                personalized_html = personalized_html.replace("</body>", f"{tracking_pixel}</body>")
            else:
                personalized_html += tracking_pixel
            
            # Create email tracker
            tracker = EmailTracker(
                id=tracker_id,
                campaign_id=campaign.id,
                user_id=current_user.id,
                recipient_email=contact.email,
                sender_email="noreply@yourdomain.com",  # Configure this
                subject=email_subject,
                html_content=personalized_html,
                text_content=personalized_text,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            db.add(tracker)
            db.commit()
            
            # Prepare email request
            email_request = EmailSendRequest(
                to_email=contact.email,
                from_email="noreply@yourdomain.com",  # Configure this
                from_name="Campaign System",
                subject=email_subject,
                html_content=personalized_html,
                text_content=personalized_text
            )
            
            # Send email
            success = await email_service.send_email(email_request, tracker_id, tracking_pixel_url)
            
            if success:
                # Mark as delivered
                tracker.delivered = True
                tracker.delivered_at = datetime.now()
                db.commit()
                
                sent_count += 1
                print(f"✅ Email sent successfully to {contact.email}")
            else:
                # Mark as failed
                tracker.delivered = False
                tracker.failed_at = datetime.now()
                db.commit()
                
                failed_count += 1
                print(f"❌ Failed to send email to {contact.email}")
                
        except Exception as e:
            failed_count += 1
            print(f"❌ Error sending to {contact.email}: {e}")
    
    # Update campaign final status
    if sent_count > 0:
        campaign.status = "sent"
        campaign.sent_count = sent_count
    else:
        campaign.status = "failed"
        campaign.sent_count = 0
    
    # Update template usage count if template was used
    if template:
        template.usage_count = (template.usage_count or 0) + 1
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Campaign send completed. {sent_count} emails sent, {failed_count} failed.",
        "campaign_id": campaign.id,
        "status": campaign.status,
        "sent_count": sent_count,
        "failed_count": failed_count
    }


@router.post("/{campaign_id}/schedule", summary="Schedule campaign")
async def schedule_campaign(
    campaign_id: str,
    schedule_data: schemas.CampaignSchedule,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Schedule a campaign for future sending with timezone support.
    
    The endpoint accepts a datetime and timezone, converts it to UTC for storage,
    and saves both the UTC time and the original timezone for proper display.
    """
    import pytz
    
    try:
        campaign = db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.user_id == current_user.id
        ).first()
        
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        
        if campaign.status != "draft":
            raise HTTPException(
                status_code=400,
                detail="Only draft campaigns can be scheduled"
            )
        
        # Handle timezone conversion
        user_timezone = schedule_data.timezone or "UTC"
        scheduled_time = schedule_data.scheduled_at
        
        try:
            # Get timezone object
            if user_timezone == "UTC":
                tz = timezone.utc
            else:
                tz = pytz.timezone(user_timezone)
            
            # Convert the scheduled time to the user's timezone if it's naive
            if scheduled_time.tzinfo is None:
                # Assume the naive datetime is in the user's specified timezone
                if hasattr(tz, 'localize'):
                    scheduled_time_with_tz = tz.localize(scheduled_time)
                else:
                    scheduled_time_with_tz = scheduled_time.replace(tzinfo=tz)
            else:
                # Convert to the user's timezone
                scheduled_time_with_tz = scheduled_time.astimezone(tz)
            
            # Convert to UTC for storage and comparison
            scheduled_time_utc = scheduled_time_with_tz.astimezone(timezone.utc)
            
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid timezone or datetime: {str(e)}"
            )
        
        # Validate that the scheduled time is in the future (in UTC)
        now_utc = datetime.now(timezone.utc)
        
        if scheduled_time_utc <= now_utc:
            raise HTTPException(
                status_code=400,
                detail="Scheduled time must be in the future"
            )
        
        # Update campaign status and schedule
        campaign.status = "scheduled"
        # Store the scheduled time in UTC (as naive datetime for database storage)
        campaign.scheduled_at = scheduled_time_utc.replace(tzinfo=None)
        # Store the user's timezone preference
        campaign.timezone = user_timezone
        
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to schedule campaign: {str(e)}"
            )
        
        return {
            "message": "Campaign scheduled successfully",
            "campaign_id": campaign.id,
            "status": "scheduled",
            "scheduled_at": scheduled_time_utc.isoformat(),
            "scheduled_at_utc": scheduled_time_utc.isoformat(),
            "scheduled_at_user_timezone": scheduled_time_with_tz.isoformat(),
            "timezone": user_timezone,
            "utc_offset": scheduled_time_with_tz.strftime("%z")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/{campaign_id}/logs", summary="Get campaign delivery logs")
async def get_campaign_logs(
    campaign_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get detailed delivery logs for a campaign with per-recipient events.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Get email trackers for this campaign
    trackers_query = db.query(EmailTracker).filter(
        EmailTracker.campaign_id == campaign_id
    )
    
    total = trackers_query.count()
    trackers = trackers_query.offset(offset).limit(limit).all()
    
    # Format delivery logs with events for each recipient
    delivery_logs = []
    for tracker in trackers:
        # Determine current status
        if tracker.bounced:
            status = "bounced"
        elif tracker.delivered:
            status = "delivered"
        elif tracker.sent_at:
            status = "sent"
        else:
            status = "pending"
        
        # Build events timeline
        events = []
        
        # Add sent event
        if tracker.sent_at:
            events.append({
                "type": "sent",
                "timestamp": tracker.sent_at.isoformat(),
                "status": "completed"
            })
        
        # Add delivered event
        if tracker.delivered and tracker.delivered_at:
            events.append({
                "type": "delivered",
                "timestamp": tracker.delivered_at.isoformat(),
                "status": "completed"
            })
        
        # Add opened events
        if tracker.open_count > 0 and tracker.opened_at:
            events.append({
                "type": "opened",
                "timestamp": tracker.opened_at.isoformat(),
                "status": "completed",
                "count": tracker.open_count
            })
        
        # Add clicked events
        if tracker.click_count > 0 and tracker.first_click_at:
            events.append({
                "type": "clicked",
                "timestamp": tracker.first_click_at.isoformat(),
                "status": "completed",
                "count": tracker.click_count
            })
        
        # Add bounce events
        if tracker.bounced:
            # Get bounce details from EmailBounce table
            bounce = db.query(EmailBounce).filter(
                EmailBounce.tracker_id == tracker.id
            ).first()
            
            bounce_timestamp = bounce.timestamp.isoformat() if bounce else tracker.updated_at.isoformat()
            events.append({
                "type": "bounced",
                "timestamp": bounce_timestamp,
                "status": "failed",
                "reason": bounce.bounce_reason if bounce else "Email bounced"
            })
        
        # Sort events by timestamp
        events.sort(key=lambda x: x["timestamp"])
        
        delivery_logs.append({
            "recipient_email": tracker.recipient_email,
            "status": status,
            "events": events,
            "delivery_stats": {
                "sent": tracker.sent_at is not None,
                "delivered": tracker.delivered,
                "opened": tracker.open_count > 0,
                "clicked": tracker.click_count > 0,
                "bounced": tracker.bounced,
                "open_count": tracker.open_count,
                "click_count": tracker.click_count
            },
            "timestamps": {
                "sent_at": tracker.sent_at.isoformat() if tracker.sent_at else None,
                "delivered_at": tracker.delivered_at.isoformat() if tracker.delivered_at else None,
                "opened_at": tracker.opened_at.isoformat() if tracker.opened_at else None,
                "first_click_at": tracker.first_click_at.isoformat() if tracker.first_click_at else None
            }
        })
    
    return {
        "logs": delivery_logs,
        "total": total,
        "offset": offset,
        "limit": limit,
        "campaign_id": campaign_id,
        "summary": {
            "total_recipients": total,
            "sent": sum(1 for log in delivery_logs if log["delivery_stats"]["sent"]),
            "delivered": sum(1 for log in delivery_logs if log["delivery_stats"]["delivered"]),
            "opened": sum(1 for log in delivery_logs if log["delivery_stats"]["opened"]),
            "clicked": sum(1 for log in delivery_logs if log["delivery_stats"]["clicked"]),
            "bounced": sum(1 for log in delivery_logs if log["delivery_stats"]["bounced"])
        }
    }


@router.get("/{campaign_id}/auto-save", summary="Get auto-save data")
async def get_auto_save_data(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get auto-save data for a campaign.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Return auto-save data
    auto_save_data = {
        "last_saved_at": campaign.updated_at.isoformat(),
        "draft_content": {
            "name": campaign.name,
            "subject": campaign.subject,
            "description": campaign.description,
            "status": campaign.status
        }
    }
    
    return auto_save_data


@router.post("/{campaign_id}/auto-save", summary="Auto-save campaign")
async def auto_save_campaign(
    campaign_id: str,
    request_data: dict,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Auto-save campaign changes.
    """
    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_id,
        Campaign.user_id == current_user.id
    ).first()
    
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    
    # Extract draft data from request
    draft_data = request_data.get('draft_data', {})
    
    # Update the campaign with new data
    for field, value in draft_data.items():
        if hasattr(campaign, field) and field not in ['id', 'user_id', 'created_at']:
            setattr(campaign, field, value)
    
    # Update timestamp
    campaign.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(campaign)
    
    return {
        "success": True,
        "saved_at": campaign.updated_at.isoformat()
    }
