import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formataddr
from email import encoders
import re
import os
import uuid
from typing import Optional
import logging
from datetime import datetime
import base64
import certifi

from ..database.models import EmailTracker
from ..schemas.email import EmailSendRequest
from ..config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.smtp_server
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password.strip()  # Remove any whitespace
        self.base_url = settings.base_url
        self.smtp_use_tls = settings.smtp_use_tls
        self.smtp_use_ssl = settings.smtp_use_ssl
        # SSL verification setting (set to False for development/testing if needed)
        self.verify_ssl = settings.verify_ssl
        
        # Debug logging for configuration
        logger.info(f"SMTP Config: server={self.smtp_server}, port={self.smtp_port}, "
                   f"username={self.smtp_username}, use_tls={self.smtp_use_tls}, "
                   f"use_ssl={self.smtp_use_ssl}, verify_ssl={self.verify_ssl}")
        
    def create_ssl_context(self):
        """Create SSL context with proper certificate handling"""
        try:
            # Try to create context with system certificates
            context = ssl.create_default_context()
            
            # Use certifi certificates if available
            try:
                context.load_verify_locations(certifi.where())
            except:
                pass
            
            # If SSL verification is disabled, allow unverified connections
            if not self.verify_ssl:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                logger.warning("SSL certificate verification is disabled")
            
            return context
        except Exception as e:
            logger.warning(f"Failed to create SSL context with certificates: {e}")
            # Fallback to unverified context for development
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            return context
        
    def add_tracking_pixel(self, html_content: str, tracking_pixel_url: str) -> str:
        """Add tracking pixel to HTML content"""
        if not html_content:
            return html_content
            
        tracking_pixel = f'<img src="{tracking_pixel_url}" width="1" height="1" style="display:none;" />'
        
        # Try to insert before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{tracking_pixel}</body>')
        else:
            # If no body tag, append at the end
            html_content += tracking_pixel
            
        return html_content
    
    def add_click_tracking(self, html_content: str, tracker_id: str) -> str:
        """Add click tracking to all links in HTML content"""
        if not html_content:
            return html_content
            
        # Find all href attributes
        def replace_link(match):
            original_url = match.group(1)
            # Skip if it's already a tracking link or a mailto link
            if self.base_url in original_url or original_url.startswith('mailto:'):
                return match.group(0)
            
            # Create tracking URL
            tracking_url = f"{self.base_url}/track/click/{tracker_id}?url={original_url}"
            return f'href="{tracking_url}"'
        
        # Replace all href attributes
        html_content = re.sub(r'href="([^"]*)"', replace_link, html_content)
        html_content = re.sub(r"href='([^']*)'", replace_link, html_content)
        
        return html_content
    
    def create_unsubscribe_link(self, tracker_id: str) -> str:
        """Create unsubscribe link"""
        return f"{self.base_url}/unsubscribe/{tracker_id}"
    
    def add_unsubscribe_footer(self, html_content: str, tracker_id: str) -> str:
        """Add unsubscribe footer to HTML content"""
        if not html_content:
            return html_content
            
        unsubscribe_link = self.create_unsubscribe_link(tracker_id)
        footer = f'''
        <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; font-size: 12px; color: #666;">
            <p>You received this email because you subscribed to our mailing list.</p>
            <p><a href="{unsubscribe_link}" style="color: #666;">Unsubscribe</a> from future emails.</p>
        </div>
        '''
        
        # Try to insert before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{footer}</body>')
        else:
            html_content += footer
            
        return html_content

    async def send_email(self, email_request: EmailSendRequest, tracker_id: str, tracking_pixel_url: str) -> bool:
        """Send email with tracking and improved SSL handling"""
        try:
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = email_request.subject
            message['From'] = formataddr((email_request.from_name, email_request.from_email))
            message['To'] = email_request.to_email
            
            if email_request.reply_to:
                message['Reply-To'] = email_request.reply_to
            
            # Add text content
            if email_request.text_content:
                text_part = MIMEText(email_request.text_content, 'plain')
                message.attach(text_part)
            
            # Add HTML content with tracking
            if email_request.html_content:
                html_content = email_request.html_content
                html_content = self.add_tracking_pixel(html_content, tracking_pixel_url)
                html_content = self.add_click_tracking(html_content, tracker_id)
                html_content = self.add_unsubscribe_footer(html_content, tracker_id)
                html_part = MIMEText(html_content, 'html')
                message.attach(html_part)
            
            # Send email with SSL context
            context = self.create_ssl_context()
            success = False
            last_error = None

            # Use the configured SMTP method
            if self.smtp_use_ssl and self.smtp_port == 465:
                # Direct SSL connection (usually port 465)
                try:
                    with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context, timeout=10) as server:
                        server.login(self.smtp_username, self.smtp_password)
                        server.send_message(message)
                        success = True
                        logger.info(f"Email sent via SSL to {email_request.to_email}")
                except Exception as e:
                    last_error = e
                    logger.error(f"SSL attempt failed: {e}")
            
            elif self.smtp_use_tls and self.smtp_port == 587:
                # STARTTLS connection (usually port 587)
                try:
                    with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                        server.starttls(context=context)
                        server.login(self.smtp_username, self.smtp_password)
                        server.send_message(message)
                        success = True
                        logger.info(f"Email sent via STARTTLS to {email_request.to_email}")
                except Exception as e:
                    last_error = e
                    logger.error(f"STARTTLS attempt failed: {e}")
            
            else:
                # Fallback: try both methods
                # Try STARTTLS first
                try:
                    with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                        if self.smtp_use_tls:
                            server.starttls(context=context)
                        server.login(self.smtp_username, self.smtp_password)
                        server.send_message(message)
                        success = True
                        logger.info(f"Email sent via STARTTLS to {email_request.to_email}")
                except Exception as e:
                    last_error = e
                    logger.warning(f"STARTTLS attempt failed: {e}")

                # Try direct SSL if STARTTLS failed and SSL is enabled
                if not success and self.smtp_use_ssl:
                    try:
                        ssl_port = 465 if self.smtp_port == 587 else self.smtp_port
                        with smtplib.SMTP_SSL(self.smtp_server, ssl_port, context=context, timeout=10) as server:
                            server.login(self.smtp_username, self.smtp_password)
                            server.send_message(message)
                            success = True
                            logger.info(f"Email sent via SSL to {email_request.to_email}")
                    except Exception as e:
                        last_error = e
                        logger.warning(f"SSL attempt failed: {e}")

            # Update tracker status in database
            if success:
                try:
                    from ..database.connection import SessionLocal
                    db = SessionLocal()
                    try:
                        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
                        if tracker:
                            tracker.delivered = True
                            tracker.sent_at = datetime.utcnow()
                            tracker.updated_at = datetime.utcnow()
                            db.commit()
                            logger.info(f"Tracker updated for {email_request.to_email}")
                    finally:
                        db.close()
                except Exception as db_error:
                    logger.error(f"Failed to update tracker: {db_error}")

            if not success:
                raise last_error or Exception("Failed to send email")

            return True

        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"Failed to send email to {email_request.to_email}: {error_str}")
            
            # Check if this is a bounce (permanent failure)
            bounce_indicators = [
                'mailbox unavailable', 'user unknown', 'invalid recipient',
                'address not found', 'recipient rejected', 'mailbox not found',
                'no such user', 'user not found', 'invalid address',
                'delivery to the following recipient failed permanently'
            ]
            
            is_bounce = any(indicator in error_str for indicator in bounce_indicators)
            
            if is_bounce:
                # This is likely a hard bounce, record it
                try:
                    from ..database.connection import SessionLocal
                    from ..database.models import EmailTracker, EmailBounce
                    
                    db = SessionLocal()
                    try:
                        tracker = db.query(EmailTracker).filter(EmailTracker.id == tracker_id).first()
                        if tracker:
                            tracker.bounced = True
                            tracker.bounce_reason = str(e)[:500]  # Limit length
                            tracker.updated_at = datetime.utcnow()
                            
                            # Create bounce record
                            bounce = EmailBounce(
                                id=str(uuid.uuid4()),
                                tracker_id=tracker_id,
                                bounce_type="hard",
                                reason=str(e)[:500],
                                timestamp=datetime.utcnow()
                            )
                            db.add(bounce)
                            db.commit()
                            logger.info(f"Recorded hard bounce for {email_request.to_email}")
                    finally:
                        db.close()
                except Exception as db_error:
                    logger.error(f"Failed to record bounce: {db_error}")
            
            return False
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return re.match(pattern, email) is not None
    
    def get_email_provider(self, email: str) -> str:
        """Get email provider from email address"""
        domain = email.split('@')[1].lower()
        
        providers = {
            'gmail.com': 'Gmail',
            'yahoo.com': 'Yahoo',
            'outlook.com': 'Outlook',
            'hotmail.com': 'Hotmail',
            'icloud.com': 'iCloud',
            'aol.com': 'AOL'
        }
        
        return providers.get(domain, 'Other')
    
    def create_email_template(self, template_name: str, subject: str, html_content: str, text_content: str = None) -> dict:
        """Create email template data"""
        return {
            'name': template_name,
            'subject': subject,
            'html_content': html_content,
            'text_content': text_content or self.html_to_text(html_content),
            'created_at': datetime.utcnow()
        }
    
    def html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text"""
        if not html_content:
            return ""
        
        # Simple HTML to text conversion
        # Remove HTML tags
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def personalize_content(self, content: str, recipient_data: dict) -> str:
        """Personalize email content with recipient data"""
        if not content or not recipient_data:
            return content
        
        # Replace placeholders like {{first_name}}, {{last_name}}, etc.
        for key, value in recipient_data.items():
            placeholder = f"{{{{{key}}}}}"
            content = content.replace(placeholder, str(value))
        
        return content
    
    def schedule_email(self, email_request: EmailSendRequest, send_at: datetime) -> dict:
        """Schedule email for later sending"""
        return {
            'email_request': email_request,
            'send_at': send_at,
            'status': 'scheduled',
            'created_at': datetime.utcnow()
        }
    
    def create_campaign_report(self, campaign_id: str, analytics_data: dict) -> str:
        """Create HTML campaign report"""
        html_report = f"""
        <html>
        <head>
            <title>Campaign Report - {campaign_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f4f4f4; padding: 20px; margin-bottom: 20px; }}
                .metric {{ display: inline-block; margin: 10px; padding: 15px; background-color: #e9e9e9; }}
                .metric-value {{ font-size: 24px; font-weight: bold; color: #333; }}
                .metric-label {{ font-size: 14px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Campaign Report</h1>
                <p>Campaign ID: {campaign_id}</p>
                <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</p>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('total_sent', 0)}</div>
                    <div class="metric-label">Total Sent</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('total_opens', 0)}</div>
                    <div class="metric-label">Total Opens</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('total_clicks', 0)}</div>
                    <div class="metric-label">Total Clicks</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('open_rate', 0)}%</div>
                    <div class="metric-label">Open Rate</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('click_rate', 0)}%</div>
                    <div class="metric-label">Click Rate</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{analytics_data.get('bounce_rate', 0)}%</div>
                    <div class="metric-label">Bounce Rate</div>
                </div>
            </div>
        </body>
        </html>
        """
        return html_report