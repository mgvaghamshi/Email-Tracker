"""
User onboarding service for creating default templates and data
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List
import uuid
from datetime import datetime

from ..database.models import Template
from ..database.user_models import User
from ..core.logging_config import get_logger

logger = get_logger("services.user_onboarding")


def create_default_welcome_template(user_id: str, db: Session) -> Template:
    """
    Create a default welcome email template as a system template that appears for all users
    """
    # Check if this system template already exists
    existing_template = db.query(Template).filter(
        and_(
            Template.name == "Welcome Email - Default",
            Template.is_system_template == True
        )
    ).first()
    
    if existing_template:
        return existing_template
    
    template = Template(
        id=str(uuid.uuid4()),
        user_id=None,  # System templates don't belong to specific users
        name="Welcome Email - Default",
        type="welcome",
        status="published",
        subject="Welcome to {{company_name}}!",
        description="A warm welcome email template to get you started",
        html_content="""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome Email</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px 20px; text-align: center; border-radius: 8px 8px 0 0;">
        <h1 style="color: white; margin: 0; font-size: 28px;">Welcome to {{company_name}}!</h1>
        <p style="color: #f0f0f0; margin: 10px 0 0 0; font-size: 16px;">We're excited to have you on board</p>
    </div>
    
    <!-- Main Content -->
    <div style="background: white; padding: 40px 30px; border: 1px solid #e0e0e0; border-top: none;">
        <h2 style="color: #333; margin-bottom: 20px;">Hi {{first_name}},</h2>
        
        <p style="margin-bottom: 20px; font-size: 16px;">
            Thank you for joining our community! We're thrilled to have you as part of our growing family.
        </p>
        
        <p style="margin-bottom: 25px; font-size: 16px;">
            Here's what you can expect from us:
        </p>
        
        <!-- Benefits List -->
        <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0;">
            <ul style="margin: 0; padding-left: 20px;">
                <li style="margin-bottom: 10px; font-size: 15px;">📧 Regular updates about new features and improvements</li>
                <li style="margin-bottom: 10px; font-size: 15px;">🎯 Exclusive offers and early access to premium features</li>
                <li style="margin-bottom: 10px; font-size: 15px;">📚 Helpful tips and tutorials to maximize your experience</li>
                <li style="margin-bottom: 10px; font-size: 15px;">🛠️ Priority customer support when you need assistance</li>
            </ul>
        </div>
        
        <!-- Call to Action -->
        <div style="text-align: center; margin: 35px 0;">
            <a href="{{dashboard_link}}" style="display: inline-block; background: #4CAF50; color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 16px;">
                Get Started Now
            </a>
        </div>
        
        <p style="margin-top: 30px; font-size: 15px;">
            If you have any questions or need help getting started, don't hesitate to reach out to our support team at 
            <a href="mailto:{{support_email}}" style="color: #667eea;">{{support_email}}</a>
        </p>
        
        <p style="margin-top: 25px; font-size: 15px;">
            Welcome aboard!<br>
            <strong>The {{company_name}} Team</strong>
        </p>
    </div>
    
    <!-- Footer -->
    <div style="background: #f8f9fa; padding: 20px; text-align: center; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="margin: 0; font-size: 12px; color: #666;">
            You received this email because you signed up for {{company_name}}.<br>
            <a href="{{unsubscribe_link}}" style="color: #666;">Unsubscribe</a> | 
            <a href="{{preferences_link}}" style="color: #666;">Email Preferences</a>
        </p>
    </div>
</body>
</html>""",
        text_content="""Welcome to {{company_name}}!

Hi {{first_name}},

Thank you for joining our community! We're thrilled to have you as part of our growing family.

Here's what you can expect from us:

• Regular updates about new features and improvements
• Exclusive offers and early access to premium features  
• Helpful tips and tutorials to maximize your experience
• Priority customer support when you need assistance

Get started by visiting your dashboard: {{dashboard_link}}

If you have any questions or need help getting started, don't hesitate to reach out to our support team at {{support_email}}

Welcome aboard!
The {{company_name}} Team

---
You received this email because you signed up for {{company_name}}.
Unsubscribe: {{unsubscribe_link}} | Email Preferences: {{preferences_link}}""",
        thumbnail_url=None,
        tags="welcome,onboarding,new-user,default,system",
        folder="System Templates",
        usage_count=0,
        version=1,
        is_locked=False,
        is_system_template=True,  # Make this a system template
        parent_template_id=None,
        last_used_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return template


def create_default_newsletter_template(user_id: str, db: Session) -> Template:
    """
    Create a default newsletter template as a system template that appears for all users
    """
    # Check if this system template already exists
    existing_template = db.query(Template).filter(
        and_(
            Template.name == "Monthly Newsletter - Default",
            Template.is_system_template == True
        )
    ).first()
    
    if existing_template:
        return existing_template
    
    template = Template(
        id=str(uuid.uuid4()),
        user_id=None,  # System templates don't belong to specific users
        name="Monthly Newsletter - Default",
        type="newsletter",
        status="published",
        subject="{{company_name}} - {{month}} Newsletter",
        description="A professional newsletter template for regular updates",
        html_content="""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Newsletter</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; background-color: #f4f4f4;">
    
    <!-- Header -->
    <div style="background: white; padding: 30px 20px; text-align: center; border-bottom: 3px solid #007bff;">
        <h1 style="color: #007bff; margin: 0; font-size: 32px; font-weight: 300;">{{company_name}}</h1>
        <p style="color: #666; margin: 10px 0 0 0; font-size: 18px; font-weight: 300;">{{month}} Newsletter</p>
        <p style="color: #999; margin: 5px 0 0 0; font-size: 14px;">{{date}}</p>
    </div>
    
    <!-- Main Content -->
    <div style="background: white; padding: 40px 30px;">
        
        <!-- Greeting -->
        <h2 style="color: #333; margin-bottom: 20px; font-size: 24px;">Hello {{first_name}}!</h2>
        
        <p style="margin-bottom: 30px; font-size: 16px; line-height: 1.6;">
            We hope you're doing well! Here's what's been happening at {{company_name}} this month.
        </p>
        
        <!-- Featured Article -->
        <div style="background: #f8f9fa; border-left: 4px solid #007bff; padding: 25px; margin: 30px 0;">
            <h3 style="color: #007bff; margin: 0 0 15px 0; font-size: 20px;">📰 Featured Article</h3>
            <h4 style="color: #333; margin: 0 0 10px 0; font-size: 18px;">{{featured_title}}</h4>
            <p style="margin: 0 0 15px 0; color: #666; font-size: 15px; line-height: 1.5;">
                {{featured_summary}}
            </p>
            <a href="{{featured_link}}" style="color: #007bff; text-decoration: none; font-weight: bold;">
                Read Full Article →
            </a>
        </div>
        
        <!-- News Updates -->
        <h3 style="color: #333; margin: 40px 0 20px 0; font-size: 22px; border-bottom: 2px solid #e0e0e0; padding-bottom: 10px;">
            📢 Latest Updates
        </h3>
        
        <div style="margin-bottom: 25px;">
            <h4 style="color: #333; margin: 0 0 8px 0; font-size: 16px;">{{update_1_title}}</h4>
            <p style="margin: 0 0 10px 0; color: #666; font-size: 14px; line-height: 1.5;">
                {{update_1_description}}
            </p>
            <a href="{{update_1_link}}" style="color: #007bff; text-decoration: none; font-size: 14px;">Learn more →</a>
        </div>
        
        <div style="margin-bottom: 25px;">
            <h4 style="color: #333; margin: 0 0 8px 0; font-size: 16px;">{{update_2_title}}</h4>
            <p style="margin: 0 0 10px 0; color: #666; font-size: 14px; line-height: 1.5;">
                {{update_2_description}}
            </p>
            <a href="{{update_2_link}}" style="color: #007bff; text-decoration: none; font-size: 14px;">Learn more →</a>
        </div>
        
        <!-- Community Spotlight -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 25px; border-radius: 8px; margin: 30px 0; text-align: center;">
            <h3 style="color: white; margin: 0 0 15px 0; font-size: 20px;">🌟 Community Spotlight</h3>
            <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.5;">
                {{spotlight_description}}
            </p>
            <a href="{{community_link}}" style="display: inline-block; background: rgba(255,255,255,0.2); color: white; padding: 12px 25px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                Join Our Community
            </a>
        </div>
        
        <!-- Closing -->
        <p style="margin-top: 40px; font-size: 16px; line-height: 1.6;">
            Thank you for being part of our community. We appreciate your continued support and look forward to sharing more updates with you next month!
        </p>
        
        <p style="margin-top: 25px; font-size: 15px;">
            Best regards,<br>
            <strong>The {{company_name}} Team</strong>
        </p>
    </div>
    
    <!-- Footer -->
    <div style="background: #f8f9fa; padding: 25px 20px; text-align: center; color: #666; font-size: 12px;">
        <p style="margin: 0 0 10px 0;">
            <a href="{{website_link}}" style="color: #007bff; text-decoration: none;">Visit Our Website</a> | 
            <a href="{{blog_link}}" style="color: #007bff; text-decoration: none;">Read Our Blog</a> | 
            <a href="{{social_link}}" style="color: #007bff; text-decoration: none;">Follow Us</a>
        </p>
        <p style="margin: 0;">
            You're receiving this because you subscribed to {{company_name}} newsletters.<br>
            <a href="{{unsubscribe_link}}" style="color: #666;">Unsubscribe</a> | 
            <a href="{{preferences_link}}" style="color: #666;">Update Preferences</a>
        </p>
    </div>
</body>
</html>""",
        text_content="""{{company_name}} - {{month}} Newsletter
{{date}}

Hello {{first_name}}!

We hope you're doing well! Here's what's been happening at {{company_name}} this month.

FEATURED ARTICLE
{{featured_title}}
{{featured_summary}}
Read more: {{featured_link}}

LATEST UPDATES

{{update_1_title}}
{{update_1_description}}
Learn more: {{update_1_link}}

{{update_2_title}}
{{update_2_description}}
Learn more: {{update_2_link}}

COMMUNITY SPOTLIGHT
{{spotlight_description}}
Join our community: {{community_link}}

Thank you for being part of our community. We appreciate your continued support and look forward to sharing more updates with you next month!

Best regards,
The {{company_name}} Team

---
Visit Our Website: {{website_link}}
Read Our Blog: {{blog_link}}
Follow Us: {{social_link}}

You're receiving this because you subscribed to {{company_name}} newsletters.
Unsubscribe: {{unsubscribe_link}} | Update Preferences: {{preferences_link}}""",
        thumbnail_url=None,
        tags="newsletter,monthly,updates,default,system",
        folder="System Templates",
        usage_count=0,
        version=1,
        is_locked=False,
        is_system_template=True,  # Make this a system template
        parent_template_id=None,
        last_used_at=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    return template


def create_default_templates_for_user(user: User, db: Session) -> List[Template]:
    """
    Create default system templates when a new user signs up.
    These templates are created as system templates so they appear for all users.
    
    Args:
        user: The newly created user (used for logging, templates are created as system templates)
        db: Database session
        
    Returns:
        List of created templates
    """
    logger.info(f"Creating default system templates triggered by user {user.email}")
    
    templates = []
    
    try:
        # Create welcome email template as system template
        welcome_template = create_default_welcome_template(user.id, db)
        if welcome_template.id not in [t.id for t in templates]:  # Avoid duplicates
            db.add(welcome_template)
            templates.append(welcome_template)
        
        # Create newsletter template as system template
        newsletter_template = create_default_newsletter_template(user.id, db)
        if newsletter_template.id not in [t.id for t in templates]:  # Avoid duplicates
            db.add(newsletter_template)
            templates.append(newsletter_template)
        
        # Commit all templates
        db.commit()
        
        # Refresh all templates to get their IDs
        for template in templates:
            db.refresh(template)
        
        logger.info(f"Successfully created {len(templates)} system templates available to all users (triggered by {user.email})")
        
        return templates
        
    except Exception as e:
        logger.error(f"Failed to create system templates triggered by user {user.email}: {str(e)}")
        db.rollback()
        raise


def setup_new_user_account(user: User, db: Session) -> dict:
    """
    Complete setup for a new user account including creating system templates
    
    Args:
        user: The newly created user
        db: Database session
        
    Returns:
        Dictionary with setup results
    """
    logger.info(f"Setting up new user account for {user.email}")
    
    setup_results = {
        "user_id": user.id,
        "email": user.email,
        "templates_created": 0,
        "setup_completed": False,
        "errors": []
    }
    
    try:
        # Create default system templates (if they don't already exist)
        templates = create_default_templates_for_user(user, db)
        setup_results["templates_created"] = len(templates)
        setup_results["template_ids"] = [t.id for t in templates]
        
        # Mark setup as completed
        setup_results["setup_completed"] = True
        
        logger.info(f"Successfully completed setup for user {user.email}")
        
    except Exception as e:
        error_msg = f"Error during user setup: {str(e)}"
        logger.error(error_msg)
        setup_results["errors"].append(error_msg)
    
    return setup_results
