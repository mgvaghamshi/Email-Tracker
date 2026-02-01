"""
Email notification service for security-related events.
"""
import logging
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
from datetime import datetime

logger = logging.getLogger(__name__)

async def send_security_notification_email(
    recipient_email: str,
    subject: str,
    event_type: str,
    event_details: Dict[str, Any],
    user_id: str
) -> bool:
    """
    Send security notification email to user.
    
    Args:
        recipient_email: Email address to send notification to
        subject: Email subject line
        event_type: Type of security event (password_change, login_alert, etc.)
        event_details: Details about the security event
        user_id: ID of the user the notification is for
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    try:
        # For now, just log the notification (stub implementation)
        # In production, this would integrate with your email service
        logger.info(f"Security notification email would be sent:")
        logger.info(f"  To: {recipient_email}")
        logger.info(f"  Subject: {subject}")
        logger.info(f"  Event Type: {event_type}")
        logger.info(f"  User ID: {user_id}")
        logger.info(f"  Event Details: {event_details}")
        
        # TODO: Implement actual email sending logic
        # This could use services like:
        # - SendGrid
        # - AWS SES
        # - SMTP server
        # - Other email providers
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to send security notification email: {str(e)}")
        return False

def format_security_event_email(event_type: str, event_details: Dict[str, Any]) -> tuple[str, str]:
    """
    Format email subject and body for security events.
    
    Args:
        event_type: Type of security event
        event_details: Details about the security event
        
    Returns:
        tuple: (subject, body) formatted for email
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    templates = {
        "password_change": {
            "subject": "Password Changed - EmailTracker Security Alert",
            "body": f"""
Your EmailTracker account password was changed on {timestamp}.

If this was you, no action is required.

If you did not make this change, please:
1. Log into your account immediately
2. Change your password
3. Review your security settings
4. Contact support if you need assistance

IP Address: {event_details.get('ip_address', 'Unknown')}
Browser: {event_details.get('user_agent', 'Unknown')}

Best regards,
EmailTracker Security Team
            """
        },
        "login_alert": {
            "subject": "New Login to Your EmailTracker Account",
            "body": f"""
A new login to your EmailTracker account was detected on {timestamp}.

Login Details:
- IP Address: {event_details.get('ip_address', 'Unknown')}
- Browser: {event_details.get('user_agent', 'Unknown')}
- Location: {event_details.get('location', 'Unknown')}

If this was you, no action is required.

If you don't recognize this login, please:
1. Change your password immediately
2. Review your account activity
3. Enable two-factor authentication
4. Contact support

Best regards,
EmailTracker Security Team
            """
        },
        "suspicious_activity": {
            "subject": "Suspicious Activity Detected - EmailTracker Security Alert",
            "body": f"""
Suspicious activity was detected on your EmailTracker account on {timestamp}.

Activity Details:
{event_details.get('description', 'Unknown activity')}

We recommend:
1. Review your account activity
2. Change your password if necessary
3. Enable two-factor authentication
4. Contact support if you have concerns

IP Address: {event_details.get('ip_address', 'Unknown')}
Browser: {event_details.get('user_agent', 'Unknown')}

Best regards,
EmailTracker Security Team
            """
        }
    }
    
    template = templates.get(event_type, {
        "subject": f"Security Alert - EmailTracker",
        "body": f"""
A security event occurred on your EmailTracker account on {timestamp}.

Event: {event_type}
Details: {event_details}

Please review your account and contact support if you have any concerns.

Best regards,
EmailTracker Security Team
        """
    })
    
    return template["subject"], template["body"]
