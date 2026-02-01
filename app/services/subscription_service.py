"""
Subscription and feature access service for EmailTracker API
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from datetime import datetime

from ..database.subscription_models import (
    SubscriptionPlan, 
    UserSubscription, 
    FeatureUsageLog,
    SUBSCRIPTION_FEATURES,
    assign_default_subscription
)
from ..database.user_models import User


class FeatureAccessService:
    """Service for checking feature access and subscription limits"""
    
    def __init__(self, user_id: str, db_session: Session):
        self.user_id = user_id
        self.db = db_session
        self._user_subscription = None
        self._plan = None
    
    @property
    def user_subscription(self) -> Optional[UserSubscription]:
        """Get user's current subscription"""
        if self._user_subscription is None:
            self._user_subscription = self.db.query(UserSubscription).filter(
                UserSubscription.user_id == self.user_id,
                UserSubscription.status == 'active'
            ).first()
            
            # If no subscription exists, create a default free subscription
            if not self._user_subscription:
                self._user_subscription = assign_default_subscription(self.user_id, self.db)
        
        return self._user_subscription
    
    @property
    def plan(self) -> Optional[SubscriptionPlan]:
        """Get user's current subscription plan"""
        if self._plan is None and self.user_subscription:
            self._plan = self.user_subscription.plan
        return self._plan
    
    def get_plan_name(self) -> str:
        """Get the current plan name"""
        if self.plan:
            return self.plan.name
        return 'free'
    
    def get_plan_display_name(self) -> str:
        """Get the current plan display name"""
        if self.plan:
            return self.plan.display_name
        return 'Free'
    
    # Feature Access Methods
    def can_create_campaign(self) -> bool:
        """Check if user can create more campaigns"""
        if not self.user_subscription or not self.plan:
            return False
        
        # Check for unlimited (None or -1)
        if self.plan.max_campaigns is None or self.plan.max_campaigns == -1:
            return True
        
        current_count = self.user_subscription.campaigns_used
        return current_count < self.plan.max_campaigns
    
    def can_send_to_recipients(self, recipient_count: int) -> bool:
        """Check if user can send to specified number of recipients"""
        if not self.plan:
            return False
        
        # Check for unlimited (None or -1)
        if self.plan.max_recipients_per_campaign is None or self.plan.max_recipients_per_campaign == -1:
            return True
        
        return recipient_count <= self.plan.max_recipients_per_campaign
    
    def can_send_monthly_emails(self, email_count: int = 1) -> bool:
        """Check if user can send specified number of emails this month"""
        if not self.user_subscription or not self.plan:
            return False
        
        # Check for unlimited (None or -1)
        if self.plan.max_monthly_emails is None or self.plan.max_monthly_emails == -1:
            return True
        
        current_sent = self.user_subscription.emails_sent_this_month
        return (current_sent + email_count) <= self.plan.max_monthly_emails
    
    def can_create_template(self) -> bool:
        """Check if user can create more templates"""
        if not self.user_subscription or not self.plan:
            return False
        
        # Check for unlimited (None or -1)
        if self.plan.max_templates is None or self.plan.max_templates == -1:
            return True
        
        current_count = self.user_subscription.templates_used
        return current_count < self.plan.max_templates
    
    def can_add_contacts(self, contact_count: int = 1) -> bool:
        """Check if user can add more contacts"""
        if not self.user_subscription or not self.plan:
            return False
        
        # Check for unlimited (None or -1)
        if self.plan.max_contacts is None or self.plan.max_contacts == -1:
            return True
        
        current_count = self.user_subscription.contacts_count
        return (current_count + contact_count) <= self.plan.max_contacts
    
    # Feature-specific access methods
    def can_use_ab_testing(self) -> bool:
        """Check if user can use A/B testing"""
        return self.has_feature('ab_testing')
    
    def can_use_segmentation(self) -> bool:
        """Check if user can use contact segmentation"""
        return self.has_feature('segmentation')
    
    def can_schedule_campaigns(self) -> bool:
        """Check if user can schedule campaigns"""
        return self.has_feature('campaign_scheduling')
    
    def can_use_ai_features(self) -> bool:
        """Check if user can use AI features"""
        return self.has_feature('ai_content_generation') or self.has_feature('ai_optimization')
    
    def can_use_advanced_analytics(self) -> bool:
        """Check if user can use advanced analytics"""
        return self.has_feature('advanced_analytics')
    
    def can_use_team_collaboration(self) -> bool:
        """Check if user can use team collaboration"""
        return self.has_feature('team_collaboration')
    
    def can_use_api(self) -> bool:
        """Check if user can use API access"""
        return self.has_feature('api_access')
    
    def can_use_pro_templates(self) -> bool:
        """Check if user can use professional templates"""
        return self.has_feature('pro_templates')
    
    def has_feature(self, feature: str) -> bool:
        """Check if user has access to a specific feature"""
        if not self.user_subscription or not self.plan:
            return False
        
        # Check if subscription is active
        if not self.user_subscription.is_active():
            return False
        
        return self.plan.has_feature(feature)
    
    # Usage limit getters
    def get_campaign_limit(self) -> Optional[int]:
        """Get campaign limit (None = unlimited)"""
        return self.plan.max_campaigns if self.plan else 5
    
    def get_recipient_limit(self) -> Optional[int]:
        """Get recipient per campaign limit (None = unlimited)"""
        return self.plan.max_recipients_per_campaign if self.plan else 100
    
    def get_monthly_email_limit(self) -> Optional[int]:
        """Get monthly email limit (None = unlimited)"""
        return self.plan.max_monthly_emails if self.plan else 1000
    
    def get_template_limit(self) -> Optional[int]:
        """Get template limit (None = unlimited)"""
        return self.plan.max_templates if self.plan else 3
    
    def get_contact_limit(self) -> Optional[int]:
        """Get contact limit (None = unlimited)"""
        return self.plan.max_contacts if self.plan else 500
    
    # Usage tracking methods
    def track_campaign_creation(self):
        """Track campaign creation usage"""
        if self.user_subscription:
            self.user_subscription.campaigns_used += 1
            self.db.commit()
            self._log_usage('campaign_create')
    
    def track_email_sent(self, count: int = 1):
        """Track email sending usage"""
        if self.user_subscription:
            self.user_subscription.emails_sent_this_month += count
            self.db.commit()
            self._log_usage('email_send', count)
    
    def track_template_creation(self):
        """Track template creation usage"""
        if self.user_subscription:
            self.user_subscription.templates_used += 1
            self.db.commit()
            self._log_usage('template_create')
    
    def track_contact_addition(self, count: int = 1):
        """Track contact addition usage"""
        if self.user_subscription:
            self.user_subscription.contacts_count += count
            self.db.commit()
            self._log_usage('contact_add', count)
    
    def _log_usage(self, feature_name: str, count: int = 1, metadata: Dict[str, Any] = None):
        """Log feature usage for analytics"""
        if self.user_subscription:
            usage_log = FeatureUsageLog(
                subscription_id=self.user_subscription.id,
                user_id=self.user_id,
                feature_name=feature_name,
                usage_count=count,
                metadata=str(metadata) if metadata else None
            )
            self.db.add(usage_log)
            self.db.commit()
    
    # Usage statistics
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        if not self.user_subscription or not self.plan:
            return {}
        
        stats = {
            'plan_name': self.plan.display_name,
            'plan_id': self.plan.id,
            'subscription_status': self.user_subscription.status,
            'is_trial': self.user_subscription.is_trial(),
            'days_until_renewal': self.user_subscription.days_until_renewal(),
            'usage': {
                'campaigns': {
                    'used': self.user_subscription.campaigns_used,
                    'limit': self.plan.max_campaigns,
                    'percentage': self.user_subscription.usage_percentage('campaigns')
                },
                'emails_this_month': {
                    'used': self.user_subscription.emails_sent_this_month,
                    'limit': self.plan.max_monthly_emails,
                    'percentage': self.user_subscription.usage_percentage('emails_sent_this_month')
                },
                'templates': {
                    'used': self.user_subscription.templates_used,
                    'limit': self.plan.max_templates,
                    'percentage': self.user_subscription.usage_percentage('templates')
                },
                'contacts': {
                    'used': self.user_subscription.contacts_count,
                    'limit': self.plan.max_contacts,
                    'percentage': self.user_subscription.usage_percentage('contacts_count')
                }
            },
            'features': self.plan.features_list
        }
        
        return stats
    
    def get_upgrade_suggestions(self) -> List[Dict[str, Any]]:
        """Get upgrade suggestions based on current usage"""
        suggestions = []
        
        if not self.user_subscription or not self.plan:
            return suggestions
        
        # Check if approaching limits
        if self.plan.name == 'free':
            # Check various usage patterns
            if self.user_subscription.campaigns_used >= 3:  # 60% of 5
                suggestions.append({
                    'reason': 'campaign_limit',
                    'message': 'You\'re approaching your campaign limit. Upgrade to Pro for unlimited campaigns.',
                    'recommended_plan': 'pro'
                })
            
            if self.user_subscription.emails_sent_this_month >= 500:  # 50% of 1000
                suggestions.append({
                    'reason': 'email_limit',
                    'message': 'You\'re using a lot of emails. Upgrade to Pro for 50,000 monthly emails.',
                    'recommended_plan': 'pro'
                })
        
        elif self.plan.name == 'pro':
            if self.user_subscription.emails_sent_this_month >= 40000:  # 80% of 50,000
                suggestions.append({
                    'reason': 'email_volume',
                    'message': 'High email volume detected. Consider Enterprise for unlimited emails.',
                    'recommended_plan': 'enterprise'
                })
        
        return suggestions


def require_subscription_tier(required_tier: str):
    """Decorator to require specific subscription tier"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # This will be used in FastAPI endpoints
            # Implementation depends on how the current user is passed
            pass
        return wrapper
    return decorator


def get_user_access_service(user_id: str, db_session: Session) -> FeatureAccessService:
    """Factory function to create FeatureAccessService"""
    return FeatureAccessService(user_id, db_session)
