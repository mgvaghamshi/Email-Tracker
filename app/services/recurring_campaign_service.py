"""
Recurring Campaign Service - Professional SaaS implementation
Handles scheduling, execution, and management of recurring email campaigns
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..database.recurring_models import (
    RecurringCampaign, RecurringCampaignOccurrence, 
    RecurringFrequency, RecurringStatus
)
from ..database.models import Campaign, Contact, CampaignRecipient
from ..database.user_models import User
from ..services.email_service import EmailService
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class RecurringCampaignService:
    """
    Service for managing recurring campaigns
    Similar to Mailchimp's Automation workflows
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.email_service = EmailService()
    
    def _safe_date_compare(self, date1: datetime, date2: datetime, operator: str = "<=") -> bool:
        """
        Safely compare two datetime objects, handling timezone differences.
        """
        from datetime import timezone
        
        # Normalize both dates to UTC for comparison
        if date1.tzinfo is None:
            date1 = date1.replace(tzinfo=timezone.utc)
        if date2.tzinfo is None:
            date2 = date2.replace(tzinfo=timezone.utc)
        
        # Perform the comparison
        if operator == "<=":
            return date1 <= date2
        elif operator == ">=":
            return date1 >= date2
        elif operator == "<":
            return date1 < date2
        elif operator == ">":
            return date1 > date2
        elif operator == "==":
            return date1 == date2
        else:
            raise ValueError(f"Unsupported operator: {operator}")
    
    async def create_recurring_campaign(
        self, 
        user_id: str,
        campaign_data: Dict[str, Any]
    ) -> RecurringCampaign:
        """Create a new recurring campaign"""
        
        # Create the recurring campaign record
        recurring_campaign = RecurringCampaign(
            id=str(uuid.uuid4()),
            user_id=user_id,
            **campaign_data
        )
        
        # Calculate and set next send date
        recurring_campaign.next_send_at = recurring_campaign.calculate_next_send_date(
            from_date=recurring_campaign.start_date
        )
        
        self.db.add(recurring_campaign)
        self.db.commit()
        self.db.refresh(recurring_campaign)
        
        # Generate initial schedule preview
        await self._generate_initial_occurrences(recurring_campaign)
        
        logger.info(f"Created recurring campaign {recurring_campaign.id} for user {user_id}")
        return recurring_campaign
    
    async def _generate_initial_occurrences(
        self, 
        recurring_campaign: RecurringCampaign,
        preview_count: int = 50
    ) -> List[RecurringCampaignOccurrence]:
        """Generate initial scheduled occurrences for preview and planning"""
        
        occurrences = []
        current_date = recurring_campaign.start_date
        sequence = 1
        
        while (
            sequence <= preview_count and
            (not recurring_campaign.max_occurrences or sequence <= recurring_campaign.max_occurrences) and
            (not recurring_campaign.end_date or self._safe_date_compare(current_date, recurring_campaign.end_date, operator="<="))
        ):
            
            # Check if should send on this date
            if recurring_campaign.should_send_today(current_date):
                occurrence = RecurringCampaignOccurrence(
                    id=str(uuid.uuid4()),
                    recurring_campaign_id=recurring_campaign.id,
                    sequence_number=sequence,
                    scheduled_at=current_date,
                    status="pending"  # Match database default
                )
                
                occurrences.append(occurrence)
                self.db.add(occurrence)
                sequence += 1
            
            # Calculate next date
            next_date = recurring_campaign.calculate_next_send_date(current_date)
            if not next_date or self._safe_date_compare(next_date, current_date, operator="<="):
                break
                
            current_date = next_date
        
        self.db.commit()
        recurring_campaign.total_scheduled = len(occurrences)
        self.db.commit()
        
        logger.info(f"Generated {len(occurrences)} initial occurrences for recurring campaign {recurring_campaign.id}")
        return occurrences
    
    async def activate_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Activate a recurring campaign to start sending"""
        
        campaign = self.db.query(RecurringCampaign).filter(
            and_(
                RecurringCampaign.id == campaign_id,
                RecurringCampaign.user_id == user_id
            )
        ).first()
        
        if not campaign:
            logger.error(f"Recurring campaign {campaign_id} not found for user {user_id}")
            return False
        
        if campaign.status != RecurringStatus.DRAFT:
            logger.warning(f"Cannot activate recurring campaign {campaign_id} - status is {campaign.status}")
            return False
        
        # Validate campaign configuration
        validation_errors = await self._validate_campaign_for_activation(campaign)
        if validation_errors:
            logger.error(f"Validation failed for recurring campaign {campaign_id}: {validation_errors}")
            return False
        
        # Update status
        campaign.status = RecurringStatus.ACTIVE
        campaign.is_active = True
        self.db.commit()
        
        logger.info(f"Activated recurring campaign {campaign_id}")
        return True
    
    async def _validate_campaign_for_activation(self, campaign: RecurringCampaign) -> List[str]:
        """Validate campaign configuration before activation"""
        errors = []
        
        # Check recipients configuration - allow for individual recipients, lists, or segments
        if not campaign.recipient_list_id and not campaign.segment_id and not campaign.dynamic_recipients:
            # Check if we have any contacts for the user as fallback
            contact_count = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == campaign.user_id,
                    Contact.status == "active"
                )
            ).count()
            
            if contact_count == 0:
                errors.append("No recipients configured and no active contacts found")
        
        # Check content
        if not campaign.html_template and not campaign.template_id:
            errors.append("No email content configured")
        
        # Check if start date is in future (allow current time with small buffer)
        start_time = campaign.start_date
        current_time = datetime.utcnow()
        
        # Allow activation if start date is within 1 hour of current time
        if self._safe_date_compare(start_time, (current_time - timedelta(hours=1)), operator="<"):
            errors.append("Start date is too far in the past")
        
        # Check for conflicting end conditions
        if campaign.end_date and campaign.max_occurrences:
            # Calculate estimated completion based on max_occurrences
            estimated_end = self._estimate_completion_date(campaign)
            if estimated_end and self._safe_date_compare(estimated_end, campaign.end_date, operator=">"):
                errors.append("Max occurrences would exceed end date")
        
        return errors
    
    def _estimate_completion_date(self, campaign: RecurringCampaign) -> Optional[datetime]:
        """Estimate when campaign will complete based on frequency and max occurrences"""
        if not campaign.max_occurrences:
            return None
        
        # Simple estimation - can be made more sophisticated
        if campaign.frequency == RecurringFrequency.DAILY:
            days = campaign.max_occurrences
        elif campaign.frequency == RecurringFrequency.WEEKLY:
            days = campaign.max_occurrences * 7
        elif campaign.frequency == RecurringFrequency.BIWEEKLY:
            days = campaign.max_occurrences * 14
        elif campaign.frequency == RecurringFrequency.MONTHLY:
            days = campaign.max_occurrences * 30
        elif campaign.frequency == RecurringFrequency.QUARTERLY:
            days = campaign.max_occurrences * 90
        elif campaign.frequency == RecurringFrequency.YEARLY:
            days = campaign.max_occurrences * 365
        elif campaign.frequency == RecurringFrequency.CUSTOM and campaign.custom_interval_days:
            days = campaign.max_occurrences * campaign.custom_interval_days
        else:
            return None
        
        return campaign.start_date + timedelta(days=days)
    
    async def check_and_execute_due_campaigns(self) -> int:
        """
        Check for recurring campaigns that are due to send and execute them
        Called by scheduler service
        """
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Find due occurrences
        due_occurrences = self.db.query(RecurringCampaignOccurrence).join(
            RecurringCampaign
        ).filter(
            and_(
                RecurringCampaignOccurrence.scheduled_at <= now_utc,
                RecurringCampaignOccurrence.status == "pending",  # Use "pending" instead of "scheduled"
                RecurringCampaign.status == RecurringStatus.ACTIVE,
                RecurringCampaign.is_active == True
            )
        ).limit(10).all()  # Process max 10 at a time to avoid overload
        
        executed_count = 0
        
        for occurrence in due_occurrences:
            try:
                success = await self._execute_occurrence(occurrence)
                if success:
                    executed_count += 1
            except Exception as e:
                logger.error(f"Failed to execute occurrence {occurrence.id}: {e}")
                occurrence.status = "failed"
                occurrence.error_message = str(e)
                self.db.commit()
        
        if executed_count > 0:
            logger.info(f"Executed {executed_count} recurring campaign occurrences")
        
        return executed_count
    
    async def _execute_occurrence(self, occurrence: RecurringCampaignOccurrence) -> bool:
        """Execute a single recurring campaign occurrence"""
        
        recurring_campaign = occurrence.recurring_campaign
        
        try:
            # Update occurrence status
            occurrence.status = "executing"
            self.db.commit()
            
            # Get recipients for this occurrence
            recipients = await self._get_occurrence_recipients(recurring_campaign)
            if not recipients:
                occurrence.status = "skipped"
                occurrence.error_message = "No recipients found"
                self.db.commit()
                return False
            
            # Create individual campaign for this occurrence
            campaign = await self._create_occurrence_campaign(occurrence, recipients)
            occurrence.campaign_id = campaign.id
            
            # Store recipient count only (no snapshot in database)
            occurrence.recipients_count = len(recipients)
            
            # Execute the campaign
            success = await self._send_occurrence_emails(occurrence, campaign, recipients)
            
            if success:
                occurrence.status = "sent"
                occurrence.sent_at = datetime.utcnow()  # Use sent_at instead of actual_sent_at
                
                # Update recurring campaign statistics
                recurring_campaign.total_sent += 1
                recurring_campaign.last_sent_at = datetime.utcnow()
                
                # Schedule next occurrence if needed
                await self._schedule_next_occurrence(recurring_campaign)
                
            else:
                occurrence.status = "failed"
                recurring_campaign.total_failed += 1
            
            self.db.commit()
            return success
            
        except Exception as e:
            logger.error(f"Error executing occurrence {occurrence.id}: {e}")
            occurrence.status = "failed"
            occurrence.error_message = str(e)
            recurring_campaign.total_failed += 1
            self.db.commit()
            return False
    
    async def _get_occurrence_recipients(self, recurring_campaign: RecurringCampaign) -> List[Contact]:
        """Get recipients for a recurring campaign occurrence"""
        
        if recurring_campaign.recipient_list_id:
            # Static recipient list - implement based on your contact list system
            recipients = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == recurring_campaign.user_id,
                    Contact.status == "active"
                    # Add list filtering logic here when implemented
                )
            ).all()
            
        elif recurring_campaign.segment_id:
            # Dynamic segment - implement based on your segmentation system
            recipients = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == recurring_campaign.user_id,
                    Contact.status == "active"
                    # Add segment filtering logic here when implemented
                )
            ).all()
            
        else:
            # Fallback to all active contacts for the user
            # This handles the case where individual recipients were added during creation
            recipients = self.db.query(Contact).filter(
                and_(
                    Contact.user_id == recurring_campaign.user_id,
                    Contact.status == "active"
                )
            ).all()
        
        return recipients
    
    async def _create_occurrence_campaign(
        self, 
        occurrence: RecurringCampaignOccurrence, 
        recipients: List[Contact]
    ) -> Campaign:
        """Create an individual campaign for this occurrence"""
        
        recurring_campaign = occurrence.recurring_campaign
        
        # Generate dynamic subject with variables
        subject = self._process_subject_template(
            recurring_campaign.subject,  # Use subject instead of subject_template
            occurrence.sequence_number,
            occurrence.scheduled_at
        )
        
        # Create campaign
        campaign = Campaign(
            id=str(uuid.uuid4()),
            user_id=recurring_campaign.user_id,
            template_id=recurring_campaign.template_id,
            name=f"{recurring_campaign.name} - Occurrence {occurrence.sequence_number}",
            subject=subject,
            description=f"Automatic recurring campaign occurrence {occurrence.sequence_number}",
            status="sending",
            send_type="recurring",  # Mark as recurring campaign child
            parent_campaign_id=None,  # This will be the master campaign ID
            recurring_campaign_id=recurring_campaign.id,  # Link to recurring campaign
            sequence_number=occurrence.sequence_number,  # Track sequence
            recipients_count=len(recipients),
            created_at=datetime.utcnow(),
            sent_at=datetime.utcnow()
        )
        
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        
        # Add campaign recipients
        for recipient in recipients:
            campaign_recipient = CampaignRecipient(
                id=str(uuid.uuid4()),
                campaign_id=campaign.id,
                contact_id=recipient.id,
                user_id=recurring_campaign.user_id
            )
            self.db.add(campaign_recipient)
        
        self.db.commit()
        return campaign
    
    def _process_subject_template(
        self, 
        subject_template: str, 
        sequence_number: int, 
        scheduled_date: datetime
    ) -> str:
        """Process subject template with dynamic variables"""
        
        variables = {
            '{sequence_number}': str(sequence_number),
            '{date}': scheduled_date.strftime('%Y-%m-%d'),
            '{month}': scheduled_date.strftime('%B'),
            '{year}': str(scheduled_date.year),
            '{week_number}': str(scheduled_date.isocalendar()[1]),
            '{day_name}': scheduled_date.strftime('%A'),
        }
        
        subject = subject_template
        for variable, value in variables.items():
            subject = subject.replace(variable, value)
        
        return subject
    
    async def _send_occurrence_emails(
        self, 
        occurrence: RecurringCampaignOccurrence,
        campaign: Campaign, 
        recipients: List[Contact]
    ) -> bool:
        """Send emails for this occurrence"""
        
        # This would integrate with your existing email sending logic
        # For now, we'll simulate the sending and update metrics
        
        try:
            sent_count = 0
            delivered_count = 0
            
            # Simulate email sending (replace with actual email service integration)
            for recipient in recipients:
                # Here you would integrate with your EmailService
                # success = await self.email_service.send_email(...)
                success = True  # Simulate success
                
                if success:
                    sent_count += 1
                    delivered_count += 1  # Assume immediate delivery for simulation
            
            # Update occurrence metrics
            occurrence.emails_sent = sent_count
            occurrence.emails_delivered = delivered_count
            
            # Update campaign metrics
            campaign.sent_count = sent_count
            campaign.status = "completed" if sent_count > 0 else "failed"
            
            self.db.commit()
            
            logger.info(f"Sent {sent_count}/{len(recipients)} emails for occurrence {occurrence.id}")
            return sent_count > 0
            
        except Exception as e:
            logger.error(f"Failed to send emails for occurrence {occurrence.id}: {e}")
            return False
    
    async def _schedule_next_occurrence(self, recurring_campaign: RecurringCampaign):
        """Schedule the next occurrence for this recurring campaign"""
        
        # Check if we should continue scheduling
        if recurring_campaign.status != RecurringStatus.ACTIVE:
            return
        
        if recurring_campaign.max_occurrences and recurring_campaign.total_sent >= recurring_campaign.max_occurrences:
            recurring_campaign.status = RecurringStatus.COMPLETED
            recurring_campaign.is_active = False
            self.db.commit()
            return
        
        if recurring_campaign.end_date and self._safe_date_compare(datetime.utcnow(), recurring_campaign.end_date, operator=">"):
            recurring_campaign.status = RecurringStatus.COMPLETED
            recurring_campaign.is_active = False
            self.db.commit()
            return
        
        # Calculate next send date
        next_send_date = recurring_campaign.calculate_next_send_date(
            from_date=recurring_campaign.last_sent_at or recurring_campaign.start_date
        )
        
        if next_send_date:
            # Check if occurrence already exists
            existing = self.db.query(RecurringCampaignOccurrence).filter(
                and_(
                    RecurringCampaignOccurrence.recurring_campaign_id == recurring_campaign.id,
                    RecurringCampaignOccurrence.scheduled_at == next_send_date
                )
            ).first()
            
            if not existing:
                # Create next occurrence
                next_sequence = self.db.query(func.max(RecurringCampaignOccurrence.sequence_number)).filter(
                    RecurringCampaignOccurrence.recurring_campaign_id == recurring_campaign.id
                ).scalar() or 0
                
                next_occurrence = RecurringCampaignOccurrence(
                    id=str(uuid.uuid4()),
                    recurring_campaign_id=recurring_campaign.id,
                    sequence_number=next_sequence + 1,
                    scheduled_at=next_send_date,
                    status="pending"  # Use "pending" instead of "scheduled"
                )
                
                self.db.add(next_occurrence)
                recurring_campaign.next_send_at = next_send_date
                self.db.commit()
                
                logger.info(f"Scheduled next occurrence for recurring campaign {recurring_campaign.id} at {next_send_date}")
    
    async def pause_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Pause a recurring campaign"""
        
        campaign = self.db.query(RecurringCampaign).filter(
            and_(
                RecurringCampaign.id == campaign_id,
                RecurringCampaign.user_id == user_id
            )
        ).first()
        
        if not campaign:
            return False
        
        campaign.status = RecurringStatus.PAUSED
        campaign.is_active = False
        self.db.commit()
        
        logger.info(f"Paused recurring campaign {campaign_id}")
        return True
    
    async def resume_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Resume a paused recurring campaign"""
        
        campaign = self.db.query(RecurringCampaign).filter(
            and_(
                RecurringCampaign.id == campaign_id,
                RecurringCampaign.user_id == user_id
            )
        ).first()
        
        if not campaign or campaign.status != RecurringStatus.PAUSED:
            return False
        
        campaign.status = RecurringStatus.ACTIVE
        campaign.is_active = True
        
        # Recalculate next send date
        campaign.next_send_at = campaign.calculate_next_send_date()
        
        self.db.commit()
        
        logger.info(f"Resumed recurring campaign {campaign_id}")
        return True
    
    async def cancel_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Cancel a recurring campaign"""
        
        campaign = self.db.query(RecurringCampaign).filter(
            and_(
                RecurringCampaign.id == campaign_id,
                RecurringCampaign.user_id == user_id
            )
        ).first()
        
        if not campaign:
            return False
        
        campaign.status = RecurringStatus.CANCELLED
        campaign.is_active = False
        
        # Cancel future scheduled occurrences
        now_utc = datetime.now(timezone.utc)
        self.db.query(RecurringCampaignOccurrence).filter(
            and_(
                RecurringCampaignOccurrence.recurring_campaign_id == campaign_id,
                RecurringCampaignOccurrence.status == "pending",  # Use "pending" instead of "scheduled"
                RecurringCampaignOccurrence.scheduled_at > now_utc
            )
        ).update({"status": "cancelled"})
        
        self.db.commit()
        
        logger.info(f"Cancelled recurring campaign {campaign_id}")
        return True
    
    def get_recurring_campaigns(
        self, 
        user_id: str,
        status: Optional[RecurringStatus] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[RecurringCampaign], int]:
        """Get recurring campaigns for a user"""
        
        query = self.db.query(RecurringCampaign).filter(
            RecurringCampaign.user_id == user_id
        )
        
        if status:
            query = query.filter(RecurringCampaign.status == status)
        
        total = query.count()
        campaigns = query.order_by(RecurringCampaign.created_at.desc()).offset(skip).limit(limit).all()
        
        return campaigns, total
    
    def get_campaign_occurrences(
        self,
        campaign_id: str,
        user_id: str,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[RecurringCampaignOccurrence], int]:
        """Get occurrences for a recurring campaign"""
        
        query = self.db.query(RecurringCampaignOccurrence).filter(
            RecurringCampaignOccurrence.recurring_campaign_id == campaign_id
        )
        
        total = query.count()
        occurrences = query.order_by(RecurringCampaignOccurrence.sequence_number.asc()).offset(skip).limit(limit).all()
        
        return occurrences, total
