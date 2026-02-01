"""
Unified Campaign Service - Integrates regular and recurring campaigns
Provides SaaS-standard campaign management with parent/child tracking
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from ..database.models import Campaign, Contact, CampaignRecipient
from ..database.recurring_models import RecurringCampaign, RecurringCampaignOccurrence
from ..database.user_models import User
from ..services.email_service import EmailService
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class UnifiedCampaignService:
    """
    Service for managing all campaign types in a unified way
    Bridges the gap between regular and recurring campaigns
    """
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.email_service = EmailService()
    
    def create_campaign(
        self,
        user_id: str,
        campaign_data: Dict[str, Any]
    ) -> Campaign:
        """
        Create a campaign with unified send_type handling
        
        Args:
            user_id: User ID creating the campaign
            campaign_data: Campaign configuration including send_type
            
        Returns:
            Created Campaign object
        """
        send_type = campaign_data.get('send_type', 'immediate')
        
        # Create base campaign
        campaign = Campaign(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=campaign_data.get('name'),
            subject=campaign_data.get('subject'),
            description=campaign_data.get('description'),
            template_id=campaign_data.get('template_id'),
            recipients_count=campaign_data.get('recipients_count', 0),
            status="draft",
            send_type=send_type,
            scheduled_at=campaign_data.get('scheduled_at'),
        )
        
        # Handle recurring campaigns
        if send_type == "recurring":
            campaign = self._setup_recurring_campaign(campaign, campaign_data)
        
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        
        logger.info(f"Created {send_type} campaign {campaign.id} for user {user_id}")
        return campaign
    
    def _setup_recurring_campaign(
        self,
        campaign: Campaign,
        campaign_data: Dict[str, Any]
    ) -> Campaign:
        """Setup recurring campaign configuration"""
        
        # Store recurring configuration
        recurring_config = campaign_data.get('recurring_config', {})
        campaign.recurring_config = json.dumps(recurring_config) if recurring_config else None
        campaign.recurring_start_date = campaign_data.get('recurring_start_date')
        campaign.recurring_end_date = campaign_data.get('recurring_end_date')
        campaign.recurring_max_occurrences = campaign_data.get('recurring_max_occurrences')
        
        # Calculate next send date
        if campaign.recurring_start_date:
            try:
                start_date = datetime.fromisoformat(campaign.recurring_start_date.replace('Z', '+00:00'))
                campaign.next_send_at = start_date
            except (ValueError, AttributeError):
                campaign.next_send_at = None
        
        return campaign
    
    def activate_recurring_campaign(
        self,
        campaign_id: str,
        user_id: str
    ) -> bool:
        """
        Activate a recurring campaign to start sending
        
        Args:
            campaign_id: Campaign ID to activate
            user_id: User ID (for security)
            
        Returns:
            True if activated successfully
        """
        campaign = self.db.query(Campaign).filter(
            and_(
                Campaign.id == campaign_id,
                Campaign.user_id == user_id,
                Campaign.send_type == "recurring",
                Campaign.parent_campaign_id.is_(None)  # Must be parent
            )
        ).first()
        
        if not campaign:
            logger.error(f"Recurring campaign {campaign_id} not found for user {user_id}")
            return False
        
        if campaign.status not in ["draft", "paused"]:
            logger.warning(f"Cannot activate campaign {campaign_id} - status is {campaign.status}")
            return False
        
        # Validate configuration
        if not self._validate_recurring_config(campaign):
            logger.error(f"Invalid recurring configuration for campaign {campaign_id}")
            return False
        
        try:
            # Start transaction for status synchronization
            self.db.begin()
            
            # Create or update RecurringCampaign record
            recurring_campaign = self._create_or_update_recurring_record(campaign)
            
            # Update campaign status and link to recurring record
            campaign.status = "active"  # SaaS-standard: use 'active' for active recurring campaigns
            campaign.recurring_campaign_id = recurring_campaign.id
            
            # Commit both updates in single transaction
            self.db.commit()
            
            logger.info(f"Activated recurring campaign {campaign_id} with recurring record {recurring_campaign.id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to activate recurring campaign {campaign_id}: {e}")
            return False
    
    def _create_or_update_recurring_record(self, campaign: Campaign) -> 'RecurringCampaign':
        """
        Create or update RecurringCampaign record for status synchronization
        
        Args:
            campaign: Campaign object to create recurring record for
            
        Returns:
            RecurringCampaign record
        """
        from ..database.recurring_models import RecurringCampaign, RecurringStatus, RecurringFrequency
        
        # Check if recurring record already exists
        existing_record = None
        if campaign.recurring_campaign_id:
            existing_record = self.db.query(RecurringCampaign).filter(
                RecurringCampaign.id == campaign.recurring_campaign_id
            ).first()
        
        if existing_record:
            # Update existing record
            existing_record.status = RecurringStatus.ACTIVE
            recurring_campaign = existing_record
        else:
            # Create new recurring record
            recurring_config = json.loads(campaign.recurring_config) if campaign.recurring_config else {}
            
            recurring_campaign = RecurringCampaign(
                id=str(uuid.uuid4()),
                user_id=campaign.user_id,
                campaign_id=campaign.id,
                name=campaign.name,
                status=RecurringStatus.ACTIVE,
                frequency=RecurringFrequency(recurring_config.get('frequency', 'weekly')),
                start_date=datetime.fromisoformat(campaign.recurring_start_date.replace('Z', '+00:00')) if campaign.recurring_start_date else datetime.utcnow(),
                end_date=datetime.fromisoformat(campaign.recurring_end_date.replace('Z', '+00:00')) if campaign.recurring_end_date else None,
                max_occurrences=campaign.recurring_max_occurrences,
                send_time=recurring_config.get('sendTime', '09:00'),
                timezone=recurring_config.get('timezone', 'UTC'),
                config=campaign.recurring_config or '{}'
            )
            
            self.db.add(recurring_campaign)
        
        return recurring_campaign
    
    def _validate_recurring_config(self, campaign: Campaign) -> bool:
        """Validate recurring campaign configuration"""
        
        if not campaign.recurring_config:
            return False
        
        try:
            config = json.loads(campaign.recurring_config)
            
            # Check required fields
            required_fields = ['frequency']
            for field in required_fields:
                if field not in config:
                    return False
            
            # Validate frequency
            valid_frequencies = ['daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'yearly', 'custom']
            if config['frequency'] not in valid_frequencies:
                return False
            
            # Validate start date
            if not campaign.recurring_start_date:
                return False
            
            return True
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return False
    
    def check_and_execute_due_campaigns(self) -> int:
        """
        Check for recurring campaigns that are due to send and create child campaigns
        
        Returns:
            Number of campaigns executed
        """
        now = datetime.utcnow()
        
        # Find recurring campaigns that are due to send
        due_campaigns = self.db.query(Campaign).filter(
            and_(
                Campaign.send_type == "recurring",
                Campaign.parent_campaign_id.is_(None),  # Parent campaigns only
                Campaign.status == "scheduled",  # Active recurring campaigns
                Campaign.next_send_at <= now,
                Campaign.next_send_at.isnot(None)
            )
        ).limit(10).all()  # Process max 10 at a time
        
        executed_count = 0
        
        for campaign in due_campaigns:
            try:
                success = self._execute_recurring_campaign(campaign)
                if success:
                    executed_count += 1
            except Exception as e:
                logger.error(f"Failed to execute recurring campaign {campaign.id}: {e}")
        
        if executed_count > 0:
            logger.info(f"Executed {executed_count} recurring campaigns")
        
        return executed_count
    
    def _execute_recurring_campaign(self, parent_campaign: Campaign) -> bool:
        """
        Execute a recurring campaign by creating a child campaign
        
        Args:
            parent_campaign: The recurring parent campaign
            
        Returns:
            True if executed successfully
        """
        try:
            # Get current sequence number
            current_sequence = self.db.query(func.max(Campaign.sequence_number)).filter(
                Campaign.parent_campaign_id == parent_campaign.id
            ).scalar() or 0
            
            next_sequence = current_sequence + 1
            
            # Create child campaign
            child_campaign = Campaign(
                id=str(uuid.uuid4()),
                user_id=parent_campaign.user_id,
                name=f"{parent_campaign.name} - Send {next_sequence}",
                subject=self._process_recurring_subject(parent_campaign.subject, next_sequence),
                description=f"Recurring campaign send #{next_sequence}",
                template_id=parent_campaign.template_id,
                recipients_count=parent_campaign.recipients_count,
                status="sending",
                send_type="immediate",  # Child campaigns are immediate sends
                parent_campaign_id=parent_campaign.id,
                sequence_number=next_sequence,
                created_at=datetime.utcnow(),
                sent_at=datetime.utcnow()
            )
            
            self.db.add(child_campaign)
            
            # Copy recipients from parent
            self._copy_campaign_recipients(parent_campaign.id, child_campaign.id)
            
            # Calculate next send date for parent
            self._update_next_send_date(parent_campaign)
            
            self.db.commit()
            
            logger.info(f"Created child campaign {child_campaign.id} (sequence {next_sequence}) for recurring campaign {parent_campaign.id}")
            
            # TODO: Integrate with actual email sending service
            # For now, just mark as completed
            child_campaign.status = "completed"
            self.db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute recurring campaign {parent_campaign.id}: {e}")
            self.db.rollback()
            return False
    
    def _process_recurring_subject(self, subject_template: str, sequence_number: int) -> str:
        """Process recurring subject template with variables"""
        
        # Replace common variables
        variables = {
            '{sequence}': str(sequence_number),
            '{sequence_number}': str(sequence_number),
            '{date}': datetime.utcnow().strftime('%Y-%m-%d'),
            '{month}': datetime.utcnow().strftime('%B'),
            '{year}': str(datetime.utcnow().year),
        }
        
        processed_subject = subject_template
        for variable, value in variables.items():
            processed_subject = processed_subject.replace(variable, value)
        
        return processed_subject
    
    def _copy_campaign_recipients(self, parent_campaign_id: str, child_campaign_id: str):
        """Copy recipients from parent campaign to child campaign"""
        
        parent_recipients = self.db.query(CampaignRecipient).filter(
            CampaignRecipient.campaign_id == parent_campaign_id
        ).all()
        
        for parent_recipient in parent_recipients:
            child_recipient = CampaignRecipient(
                id=str(uuid.uuid4()),
                campaign_id=child_campaign_id,
                contact_id=parent_recipient.contact_id,
                user_id=parent_recipient.user_id,
                created_at=datetime.utcnow()
            )
            self.db.add(child_recipient)
    
    def _update_next_send_date(self, parent_campaign: Campaign):
        """Update next send date for recurring campaign"""
        
        try:
            config = json.loads(parent_campaign.recurring_config or '{}')
            frequency = config.get('frequency', 'daily')
            
            current_next_send = parent_campaign.next_send_at
            if not current_next_send:
                return
            
            # Calculate next send date based on frequency
            if frequency == 'daily':
                next_send = current_next_send + timedelta(days=1)
            elif frequency == 'weekly':
                next_send = current_next_send + timedelta(weeks=1)
            elif frequency == 'biweekly':
                next_send = current_next_send + timedelta(weeks=2)
            elif frequency == 'monthly':
                # Approximate month increment
                next_send = current_next_send + timedelta(days=30)
            elif frequency == 'quarterly':
                next_send = current_next_send + timedelta(days=90)
            elif frequency == 'yearly':
                next_send = current_next_send + timedelta(days=365)
            elif frequency == 'custom':
                interval_days = config.get('custom_interval_days', 1)
                next_send = current_next_send + timedelta(days=interval_days)
            else:
                return
            
            # Check if we should continue scheduling
            if self._should_continue_recurring(parent_campaign, next_send):
                parent_campaign.next_send_at = next_send
            else:
                # Complete the recurring campaign
                parent_campaign.status = "completed"
                parent_campaign.next_send_at = None
                
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error(f"Failed to update next send date for campaign {parent_campaign.id}: {e}")
    
    def _should_continue_recurring(self, parent_campaign: Campaign, next_send_date: datetime) -> bool:
        """Check if recurring campaign should continue"""
        
        # Check end date
        if parent_campaign.recurring_end_date:
            try:
                end_date = datetime.fromisoformat(parent_campaign.recurring_end_date.replace('Z', '+00:00'))
                if next_send_date > end_date:
                    return False
            except (ValueError, AttributeError):
                pass
        
        # Check max occurrences
        if parent_campaign.recurring_max_occurrences:
            current_count = self.db.query(func.count(Campaign.id)).filter(
                Campaign.parent_campaign_id == parent_campaign.id
            ).scalar() or 0
            
            if current_count >= parent_campaign.recurring_max_occurrences:
                return False
        
        return True
    
    def pause_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Pause a recurring campaign with proper status synchronization"""
        
        campaign = self.db.query(Campaign).filter(
            and_(
                Campaign.id == campaign_id,
                Campaign.user_id == user_id,
                Campaign.send_type == "recurring",
                Campaign.parent_campaign_id.is_(None),
                Campaign.status == "active"  # Can only pause active campaigns
            )
        ).first()
        
        if not campaign:
            return False
        
        try:
            # Start transaction for status synchronization
            self.db.begin()
            
            # Update campaign status
            campaign.status = "paused"
            
            # Update recurring_campaigns record if it exists
            if campaign.recurring_campaign_id:
                from ..database.recurring_models import RecurringCampaign, RecurringStatus
                recurring_record = self.db.query(RecurringCampaign).filter(
                    RecurringCampaign.id == campaign.recurring_campaign_id
                ).first()
                
                if recurring_record:
                    recurring_record.status = RecurringStatus.PAUSED
            
            # Commit both updates in single transaction
            self.db.commit()
            
            logger.info(f"Paused recurring campaign {campaign_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to pause recurring campaign {campaign_id}: {e}")
            return False
    
    def resume_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Resume a paused recurring campaign with proper status synchronization"""
        
        campaign = self.db.query(Campaign).filter(
            and_(
                Campaign.id == campaign_id,
                Campaign.user_id == user_id,
                Campaign.send_type == "recurring",
                Campaign.parent_campaign_id.is_(None),
                Campaign.status == "paused"  # Can only resume paused campaigns
            )
        ).first()
        
        if not campaign:
            return False
        
        try:
            # Start transaction for status synchronization
            self.db.begin()
            
            # Update campaign status
            campaign.status = "active"
            
            # Recalculate next send date if needed
            if not campaign.next_send_at:
                self._update_next_send_date(campaign)
            
            # Update recurring_campaigns record if it exists
            if campaign.recurring_campaign_id:
                from ..database.recurring_models import RecurringCampaign, RecurringStatus
                recurring_record = self.db.query(RecurringCampaign).filter(
                    RecurringCampaign.id == campaign.recurring_campaign_id
                ).first()
                
                if recurring_record:
                    recurring_record.status = RecurringStatus.ACTIVE
            
            # Commit both updates in single transaction
            self.db.commit()
            
            logger.info(f"Resumed recurring campaign {campaign_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to resume recurring campaign {campaign_id}: {e}")
            return False
    
    def stop_recurring_campaign(self, campaign_id: str, user_id: str) -> bool:
        """Stop a recurring campaign permanently with proper status synchronization"""
        
        campaign = self.db.query(Campaign).filter(
            and_(
                Campaign.id == campaign_id,
                Campaign.user_id == user_id,
                Campaign.send_type == "recurring",
                Campaign.parent_campaign_id.is_(None),
                Campaign.status.in_(["active", "paused"])  # Can stop active or paused campaigns
            )
        ).first()
        
        if not campaign:
            return False
        
        try:
            # Start transaction for status synchronization
            self.db.begin()
            
            # Update campaign status
            campaign.status = "stopped"
            campaign.next_send_at = None  # Clear next send date
            
            # Update recurring_campaigns record if it exists
            if campaign.recurring_campaign_id:
                from ..database.recurring_models import RecurringCampaign, RecurringStatus
                recurring_record = self.db.query(RecurringCampaign).filter(
                    RecurringCampaign.id == campaign.recurring_campaign_id
                ).first()
                
                if recurring_record:
                    recurring_record.status = RecurringStatus.CANCELLED
            
            # Commit both updates in single transaction
            self.db.commit()
            
            logger.info(f"Stopped recurring campaign {campaign_id}")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to stop recurring campaign {campaign_id}: {e}")
            return False
