"""
Campaign Scheduler Service

This service runs in the background and checks for scheduled campaigns
that need to be sent, then executes them automatically.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database.connection import get_db
from ..database.models import Campaign
from ..database.user_models import User
from ..api.v1.campaigns import send_campaign as _send_campaign_endpoint

logger = logging.getLogger(__name__)


class CampaignScheduler:
    """Background scheduler for executing scheduled campaigns"""
    
    def __init__(self, check_interval: int = 60):
        """
        Initialize scheduler
        
        Args:
            check_interval: How often to check for scheduled campaigns (seconds)
        """
        self.check_interval = check_interval
        self.running = False
        self._task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the scheduler"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self._task = asyncio.create_task(self._run_scheduler())
        logger.info(f"Campaign scheduler started with {self.check_interval}s check interval")
    
    async def stop(self):
        """Stop the scheduler"""
        if not self.running:
            return
        
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("Campaign scheduler stopped")
    
    async def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                await self._check_and_execute_campaigns()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute_campaigns(self):
        """Check for scheduled campaigns that need to be sent"""
        db = next(get_db())
        try:
            # Get current time in UTC
            now_utc = datetime.now(timezone.utc)
            
            # Find campaigns that are scheduled and due to be sent
            scheduled_campaigns = db.query(Campaign).filter(
                and_(
                    Campaign.status == "scheduled",
                    Campaign.scheduled_at <= now_utc.replace(tzinfo=None),  # Database stores naive UTC
                    Campaign.scheduled_at.isnot(None)
                )
            ).all()
            
            if scheduled_campaigns:
                logger.info(f"Found {len(scheduled_campaigns)} campaigns ready to send")
            
            for campaign in scheduled_campaigns:
                try:
                    await self._execute_campaign(campaign, db)
                except Exception as e:
                    logger.error(f"Failed to execute campaign {campaign.id}: {e}")
                    # Mark campaign as failed
                    campaign.status = "failed"
                    db.commit()
        
        except Exception as e:
            logger.error(f"Error checking scheduled campaigns: {e}")
        finally:
            db.close()
    
    async def _execute_campaign(self, campaign: Campaign, db: Session):
        """Execute a specific campaign"""
        logger.info(f"Executing scheduled campaign: {campaign.id} - {campaign.name}")
        
        try:
            # Get the campaign owner
            user = db.query(User).filter(User.id == campaign.user_id).first()
            if not user:
                logger.error(f"User not found for campaign {campaign.id}")
                campaign.status = "failed"
                db.commit()
                return
            
            # Import the required modules for sending
            from ..services.email_service import EmailService
            from ..database.models import CampaignRecipient, Contact, Template, EmailTracker
            from ..schemas.email import EmailSendRequest
            from ..api.v1.settings import load_setting
            import uuid
            import re
            
            # Check if campaign can be sent
            if campaign.status != "scheduled":
                logger.warning(f"Campaign {campaign.id} is not in scheduled status: {campaign.status}")
                return
            
            # Get campaign recipients
            recipients = db.query(CampaignRecipient).join(Contact).filter(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.user_id == user.id,
                Contact.status == 'active'
            ).all()
            
            if not recipients:
                logger.error(f"Campaign {campaign.id} has no recipients")
                campaign.status = "failed"
                db.commit()
                return
            
            # Get template if specified
            template = None
            if campaign.template_id:
                template = db.query(Template).filter(
                    Template.id == campaign.template_id,
                    Template.user_id == user.id
                ).first()
            
            # Update campaign status to sending
            campaign.status = "sending"
            campaign.sent_at = datetime.now()
            db.commit()
            
            # Initialize email service
            email_service = EmailService()
            sent_count = 0
            failed_count = 0
            
            # Prepare email content (similar to send_campaign endpoint)
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
            try:
                company_settings = load_setting("company", default_company, user.id)
            except:
                company_settings = default_company
                
            company_name = company_settings.get("company_name", "Your Company")
            company_email = company_settings.get("support_email", "noreply@yourdomain.com")
            company_website = company_settings.get("company_website", "https://yourcompany.com")
            company_address = company_settings.get("company_address", "123 Business St, City, State 12345")
            base_url = email_service.base_url
            
            # Prepare email content based on template or campaign description
            if template and template.html_content:
                html_content_template = template.html_content
                text_content_template = template.text_content or ""
                
                if template.subject and not email_subject:
                    email_subject = template.subject
                
                # Replace template variables
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
                
                for variable, value in template_variables.items():
                    html_content_template = html_content_template.replace(variable, value)
                    text_content_template = text_content_template.replace(variable, value)
            else:
                # Fallback template
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
                    tracking_pixel_url = f"{email_service.base_url}/track/{tracker_id}"
                    
                    # Personalize content
                    first_name = contact.first_name or "there"
                    
                    personalization_vars = {
                        '{{first_name}}': first_name,
                        '{{company_name}}': company_name,
                        '{{campaign_name}}': campaign.name,
                        '{{campaign_description}}': campaign.description or "",
                        '{{unsubscribe_url}}': f"{base_url}/unsubscribe/{tracker_id}",
                        '{{company_email}}': company_email,
                        '{{year}}': str(datetime.now().year),
                        '{{tracker_id}}': tracker_id
                    }
                    
                    personalized_html = html_content_template
                    personalized_text = text_content_template
                    
                    for variable, value in personalization_vars.items():
                        personalized_html = personalized_html.replace(variable, str(value))
                        personalized_text = personalized_text.replace(variable, str(value))
                    
                    # Add tracking pixel
                    tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" alt="" />'
                    if "</body>" in personalized_html:
                        personalized_html = personalized_html.replace("</body>", f"{tracking_pixel}</body>")
                    else:
                        personalized_html += tracking_pixel
                    
                    # Create email tracker
                    tracker = EmailTracker(
                        id=tracker_id,
                        campaign_id=campaign.id,
                        user_id=user.id,
                        recipient_email=contact.email,
                        sender_email="noreply@yourdomain.com",
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
                        from_email="noreply@yourdomain.com",
                        from_name="Campaign System",
                        subject=email_subject,
                        html_content=personalized_html,
                        text_content=personalized_text
                    )
                    
                    # Send email
                    success = await email_service.send_email(email_request, tracker_id, tracking_pixel_url)
                    
                    if success:
                        sent_count += 1
                        logger.debug(f"✅ Email sent successfully to {contact.email}")
                    else:
                        failed_count += 1
                        logger.warning(f"❌ Failed to send email to {contact.email}")
                        
                except Exception as e:
                    failed_count += 1
                    logger.error(f"❌ Error sending to {contact.email}: {e}")
            
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
            
            logger.info(f"Campaign {campaign.id} executed: {sent_count} sent, {failed_count} failed")
            
        except Exception as e:
            logger.error(f"Error executing campaign {campaign.id}: {e}")
            campaign.status = "failed"
            db.commit()
            raise


# Global scheduler instance
scheduler = CampaignScheduler()


async def start_scheduler():
    """Start the global scheduler"""
    await scheduler.start()


async def stop_scheduler():
    """Stop the global scheduler"""
    await scheduler.stop()


def get_scheduler() -> CampaignScheduler:
    """Get the global scheduler instance"""
    return scheduler
