"""
Subscription and tier management models for EmailTracker API
"""
import uuid
import json
from sqlalchemy import (
    Column, String, Text, Boolean, Integer, DateTime, 
    ForeignKey, Index, Float, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from ..models import Base


class SubscriptionPlan(Base):
    """Subscription plan model defining tier features and limits"""
    __tablename__ = "subscription_plans"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Plan identification
    name = Column(String, nullable=False, unique=True)  # 'free', 'pro', 'enterprise'
    display_name = Column(String, nullable=False)  # 'Free', 'Pro', 'Enterprise'
    description = Column(Text, nullable=True)
    
    # Pricing
    price = Column(Float, nullable=False, default=0.0)
    billing_interval = Column(String, nullable=False, default='monthly')  # 'monthly', 'yearly'
    
    # Campaign limits
    max_campaigns = Column(Integer, nullable=True)  # NULL = unlimited
    max_recipients_per_campaign = Column(Integer, nullable=True)  # NULL = unlimited
    max_monthly_emails = Column(Integer, nullable=True)  # NULL = unlimited
    max_templates = Column(Integer, nullable=True)  # NULL = unlimited
    max_contacts = Column(Integer, nullable=True)  # NULL = unlimited
    
    # Feature flags (JSON array of enabled features)
    features = Column(Text, nullable=False, default='[]')
    
    # Plan settings
    is_active = Column(Boolean, default=True)
    is_popular = Column(Boolean, default=False)  # For marketing/UI display
    sort_order = Column(Integer, default=0)  # For ordering plans in UI
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user_subscriptions = relationship("UserSubscription", back_populates="plan", cascade="all, delete-orphan")
    
    @property
    def features_list(self) -> List[str]:
        """Get features as a list"""
        if self.features:
            try:
                return json.loads(self.features)
            except (json.JSONDecodeError, TypeError):
                return []
        return []
    
    @features_list.setter
    def features_list(self, value: List[str]):
        """Set features from a list"""
        self.features = json.dumps(value) if value else '[]'
    
    def has_feature(self, feature: str) -> bool:
        """Check if plan has a specific feature"""
        return feature in self.features_list
    
    def get_display_price(self) -> str:
        """Get formatted price for display"""
        if self.price == 0:
            return "Free"
        elif self.billing_interval == 'yearly':
            monthly_price = self.price / 12
            return f"${self.price:.0f}/year (${monthly_price:.0f}/month)"
        else:
            return f"${self.price:.0f}/month"
    
    __table_args__ = (
        Index('idx_subscription_plan_name', 'name'),
        Index('idx_subscription_plan_active', 'is_active'),
        Index('idx_subscription_plan_sort', 'sort_order'),
    )


class UserSubscription(Base):
    """User subscription model tracking current plan and usage"""
    __tablename__ = "user_subscriptions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    plan_id = Column(String, ForeignKey("subscription_plans.id"), nullable=False)
    
    # Subscription status
    status = Column(String, nullable=False, default='active')  # 'active', 'cancelled', 'expired', 'past_due'
    
    # Billing periods
    current_period_start = Column(DateTime, nullable=False)
    current_period_end = Column(DateTime, nullable=False)
    
    # Usage tracking (reset monthly)
    campaigns_used = Column(Integer, default=0)
    emails_sent_this_month = Column(Integer, default=0)
    templates_used = Column(Integer, default=0)
    contacts_count = Column(Integer, default=0)
    
    # Billing information
    stripe_subscription_id = Column(String, nullable=True)  # For Stripe integration
    stripe_customer_id = Column(String, nullable=True)
    
    # Cancellation info
    cancel_at_period_end = Column(Boolean, default=False)
    cancelled_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    
    # Trial info
    trial_start = Column(DateTime, nullable=True)
    trial_end = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", backref="subscription")
    plan = relationship("SubscriptionPlan", back_populates="user_subscriptions")
    usage_logs = relationship("FeatureUsageLog", back_populates="subscription", cascade="all, delete-orphan")
    
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        if self.status != 'active':
            return False
        
        now = datetime.utcnow()
        
        # Check if within billing period
        if now > self.current_period_end:
            return False
        
        # Check if trial is valid (if applicable)
        if self.trial_end and now < self.trial_end:
            return True
        
        # Check if past trial but within billing period
        if self.trial_end and now > self.trial_end:
            return self.status == 'active'
        
        return True
    
    def is_trial(self) -> bool:
        """Check if user is currently in trial period"""
        if not self.trial_start or not self.trial_end:
            return False
        
        now = datetime.utcnow()
        return self.trial_start <= now <= self.trial_end
    
    def days_until_renewal(self) -> int:
        """Get days until next billing cycle"""
        now = datetime.utcnow()
        if now >= self.current_period_end:
            return 0
        
        delta = self.current_period_end - now
        return delta.days
    
    def usage_percentage(self, limit_type: str) -> float:
        """Get usage percentage for a specific limit type"""
        if not hasattr(self.plan, f'max_{limit_type}'):
            return 0.0
        
        max_value = getattr(self.plan, f'max_{limit_type}')
        if max_value is None:  # Unlimited
            return 0.0
        
        current_value = getattr(self, f'{limit_type}_used', 0)
        if max_value == 0:
            return 100.0
        
        return min((current_value / max_value) * 100, 100.0)
    
    def can_use_feature(self, feature: str) -> bool:
        """Check if user can use a specific feature"""
        return self.is_active() and self.plan.has_feature(feature)
    
    def reset_monthly_usage(self):
        """Reset monthly usage counters"""
        self.campaigns_used = 0
        self.emails_sent_this_month = 0
        self.updated_at = datetime.utcnow()
    
    __table_args__ = (
        Index('idx_user_subscription_user_id', 'user_id'),
        Index('idx_user_subscription_plan_id', 'plan_id'),
        Index('idx_user_subscription_status', 'status'),
        Index('idx_user_subscription_period_end', 'current_period_end'),
        UniqueConstraint('user_id', name='uix_user_subscription'),  # One subscription per user
    )


class FeatureUsageLog(Base):
    """Log feature usage for analytics and billing"""
    __tablename__ = "feature_usage_logs"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subscription_id = Column(String, ForeignKey("user_subscriptions.id"), nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Usage details
    feature_name = Column(String, nullable=False)  # 'campaign_create', 'email_send', etc.
    usage_count = Column(Integer, default=1)
    usage_date = Column(DateTime, default=datetime.utcnow)
    
    # Context metadata (JSON)
    feature_metadata = Column(Text, nullable=True)  # Additional context about the usage
    
    # Relationships
    subscription = relationship("UserSubscription", back_populates="usage_logs")
    user = relationship("User")
    
    __table_args__ = (
        Index('idx_usage_log_subscription', 'subscription_id'),
        Index('idx_usage_log_user', 'user_id'),
        Index('idx_usage_log_feature', 'feature_name'),
        Index('idx_usage_log_date', 'usage_date'),
        Index('idx_usage_log_user_feature_date', 'user_id', 'feature_name', 'usage_date'),
    )


# Pre-defined subscription plans and features
SUBSCRIPTION_FEATURES = {
    # Basic features (available to all tiers)
    'campaign_create': 'Create email campaigns',
    'campaign_edit': 'Edit email campaigns',
    'campaign_send': 'Send email campaigns',
    'basic_analytics': 'Basic analytics and reporting',
    'contact_management': 'Contact list management',
    'basic_templates': 'Basic email templates',
    
    # Pro features
    'campaign_scheduling': 'Schedule campaigns for future delivery',
    'ab_testing': 'A/B test campaigns',
    'advanced_analytics': 'Advanced analytics and insights',
    'segmentation': 'Contact segmentation',
    'pro_templates': 'Professional email templates',
    'email_automation': 'Basic email automation',
    'api_access': 'API access for integrations',
    'priority_support': 'Priority customer support',
    
    # Enterprise features
    'advanced_segmentation': 'Advanced AI-powered segmentation',
    'ai_content_generation': 'AI-powered content generation',
    'ai_optimization': 'AI send time and content optimization',
    'team_collaboration': 'Team collaboration and permissions',
    'campaign_approval': 'Campaign approval workflows',
    'white_labeling': 'White-label customization',
    'sso_integration': 'Single Sign-On integration',
    'advanced_integrations': 'CRM and marketing tool integrations',
    'dedicated_support': 'Dedicated customer success manager',
    'custom_limits': 'Custom usage limits and pricing',
}

# Default plan configurations
DEFAULT_PLANS = [
    {
        'name': 'free',
        'display_name': 'Free',
        'description': 'Perfect for getting started with email marketing',
        'price': 0.0,
        'billing_interval': 'monthly',
        'max_campaigns': 5,
        'max_recipients_per_campaign': 100,
        'max_monthly_emails': 1000,
        'max_templates': 3,
        'max_contacts': 500,
        'features': [
            'campaign_create',
            'campaign_edit', 
            'campaign_send',
            'basic_analytics',
            'contact_management',
            'basic_templates'
        ],
        'sort_order': 1,
        'is_popular': False
    },
    {
        'name': 'pro',
        'display_name': 'Pro',
        'description': 'Advanced features for growing businesses',
        'price': 29.0,
        'billing_interval': 'monthly',
        'max_campaigns': None,  # Unlimited
        'max_recipients_per_campaign': 10000,
        'max_monthly_emails': 50000,
        'max_templates': 50,
        'max_contacts': 10000,
        'features': [
            'campaign_create',
            'campaign_edit',
            'campaign_send',
            'basic_analytics',
            'contact_management',
            'basic_templates',
            'campaign_scheduling',
            'ab_testing',
            'advanced_analytics',
            'segmentation',
            'pro_templates',
            'email_automation',
            'api_access',
            'priority_support'
        ],
        'sort_order': 2,
        'is_popular': True
    },
    {
        'name': 'enterprise',
        'display_name': 'Enterprise',
        'description': 'Full-featured solution for large organizations',
        'price': 99.0,
        'billing_interval': 'monthly',
        'max_campaigns': None,  # Unlimited
        'max_recipients_per_campaign': None,  # Unlimited
        'max_monthly_emails': None,  # Unlimited
        'max_templates': None,  # Unlimited
        'max_contacts': None,  # Unlimited
        'features': [
            # All features
            'campaign_create',
            'campaign_edit',
            'campaign_send',
            'basic_analytics',
            'contact_management',
            'basic_templates',
            'campaign_scheduling',
            'ab_testing',
            'advanced_analytics',
            'segmentation',
            'pro_templates',
            'email_automation',
            'api_access',
            'priority_support',
            'advanced_segmentation',
            'ai_content_generation',
            'ai_optimization',
            'team_collaboration',
            'campaign_approval',
            'white_labeling',
            'sso_integration',
            'advanced_integrations',
            'dedicated_support',
            'custom_limits'
        ],
        'sort_order': 3,
        'is_popular': False
    }
]


def create_default_plans(db_session):
    """Create default subscription plans if they don't exist"""
    for plan_data in DEFAULT_PLANS:
        existing_plan = db_session.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == plan_data['name']
        ).first()
        
        if not existing_plan:
            plan = SubscriptionPlan(
                name=plan_data['name'],
                display_name=plan_data['display_name'],
                description=plan_data['description'],
                price=plan_data['price'],
                billing_interval=plan_data['billing_interval'],
                max_campaigns=plan_data['max_campaigns'],
                max_recipients_per_campaign=plan_data['max_recipients_per_campaign'],
                max_monthly_emails=plan_data['max_monthly_emails'],
                max_templates=plan_data['max_templates'],
                max_contacts=plan_data['max_contacts'],
                features=json.dumps(plan_data['features']),
                sort_order=plan_data['sort_order'],
                is_popular=plan_data['is_popular']
            )
            db_session.add(plan)
    
    db_session.commit()


def assign_default_subscription(user_id: str, db_session):
    """Assign default free subscription to a new user"""
    # Get the free plan
    free_plan = db_session.query(SubscriptionPlan).filter(
        SubscriptionPlan.name == 'free'
    ).first()
    
    if not free_plan:
        raise ValueError("Free plan not found. Please create default plans first.")
    
    # Check if user already has a subscription
    existing_subscription = db_session.query(UserSubscription).filter(
        UserSubscription.user_id == user_id
    ).first()
    
    if existing_subscription:
        return existing_subscription
    
    # Create new subscription
    now = datetime.utcnow()
    subscription = UserSubscription(
        user_id=user_id,
        plan_id=free_plan.id,
        status='active',
        current_period_start=now,
        current_period_end=now + timedelta(days=30),  # Monthly billing
        campaigns_used=0,
        emails_sent_this_month=0,
        templates_used=0,
        contacts_count=0
    )
    
    db_session.add(subscription)
    db_session.commit()
    
    return subscription


def assign_subscription_plan(user_id: str, plan_name: str, db_session):
    """
    Assign a specific subscription plan to a user
    """
    from ..core.logging_config import get_logger
    logger = get_logger("subscription_models")
    
    logger.info(f"🔍 assign_subscription_plan called with user_id={user_id}, plan_name={plan_name}")
    
    # Get the requested plan
    plan = db_session.query(SubscriptionPlan).filter(
        SubscriptionPlan.name == plan_name,
        SubscriptionPlan.is_active == True
    ).first()
    
    logger.info(f"🔍 Searched for plan '{plan_name}', found: {plan.name if plan else 'None'}")
    
    if not plan:
        logger.warning(f"⚠️ Plan '{plan_name}' not found, falling back to free plan")
        # Fallback to free plan if requested plan not found
        plan = db_session.query(SubscriptionPlan).filter(
            SubscriptionPlan.name == 'free',
            SubscriptionPlan.is_active == True
        ).first()
        
        if not plan:
            logger.error(f"❌ No valid subscription plans found.")
            raise ValueError("No valid subscription plans found.")
    
    logger.info(f"✅ Using plan: {plan.name} (id: {plan.id})")
    
    # Check if user already has a subscription
    existing_subscription = db_session.query(UserSubscription).filter(
        UserSubscription.user_id == user_id
    ).first()
    
    if existing_subscription:
        logger.info(f"🔄 User has existing subscription, updating plan from {existing_subscription.plan.name if existing_subscription.plan else 'None'} to {plan.name}")
        # Update existing subscription to new plan
        existing_subscription.plan_id = plan.id
        existing_subscription.updated_at = datetime.utcnow()
        db_session.commit()
        logger.info(f"✅ Updated existing subscription for user {user_id}")
        return existing_subscription
    
    logger.info(f"🆕 Creating new subscription for user {user_id}")
    
    # Create new subscription
    now = datetime.utcnow()
    
    # Set billing period based on plan
    if plan.billing_interval == 'yearly':
        end_date = now + timedelta(days=365)
    else:
        end_date = now + timedelta(days=30)
    
    subscription = UserSubscription(
        user_id=user_id,
        plan_id=plan.id,
        status='active',
        current_period_start=now,
        current_period_end=end_date,
        campaigns_used=0,
        emails_sent_this_month=0,
        templates_used=0,
        contacts_count=0
    )
    
    db_session.add(subscription)
    db_session.commit()
    
    logger.info(f"✅ Created new subscription for user {user_id} with plan {plan.name}")
    return subscription
