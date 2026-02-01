"""
Subscription-related Pydantic schemas
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class SubscriptionPlanResponse(BaseModel):
    """Response schema for subscription plans"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    price: float
    billing_interval: str
    display_price: str
    is_popular: bool = False
    limits: Dict[str, Optional[int]]
    features: List[str]
    sort_order: int

    class Config:
        from_attributes = True


class SubscriptionUpgrade(BaseModel):
    """Schema for subscription upgrade request"""
    plan_id: str = Field(..., description="Target subscription plan ID")
    upgrade_type: Optional[str] = Field("manual", description="Type of upgrade (manual, automatic)")
    payment_method_id: Optional[str] = Field(None, description="Payment method ID for billing")
    
    @validator('plan_id')
    def validate_plan_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Plan ID is required')
        return v.strip()


class SubscriptionCancellation(BaseModel):
    """Schema for subscription cancellation request"""
    reason: str = Field(..., description="Reason for cancellation")
    cancel_immediately: bool = Field(False, description="Cancel immediately vs at period end")
    feedback: Optional[str] = Field(None, description="Additional feedback")
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Cancellation reason is required')
        return v.strip()


class UsageStats(BaseModel):
    """Schema for usage statistics"""
    used: int
    limit: Optional[int] = None
    percentage: float
    
    class Config:
        from_attributes = True


class SubscriptionUsage(BaseModel):
    """Schema for subscription usage details"""
    campaigns: UsageStats
    emails_this_month: UsageStats
    templates: UsageStats
    contacts: UsageStats
    
    class Config:
        from_attributes = True


class SubscriptionResponse(BaseModel):
    """Response schema for subscription details"""
    id: str
    status: str
    current_period_start: datetime
    current_period_end: datetime
    is_trial: bool
    days_until_renewal: int
    cancel_at_period_end: bool = False
    
    class Config:
        from_attributes = True


class PlanResponse(BaseModel):
    """Response schema for plan details in subscription response"""
    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    price: float
    billing_interval: str
    display_price: str
    
    class Config:
        from_attributes = True


class UpgradeSuggestion(BaseModel):
    """Schema for upgrade suggestions"""
    reason: str
    message: str
    recommended_plan: str


class CurrentSubscriptionResponse(BaseModel):
    """Complete response schema for current subscription"""
    subscription: SubscriptionResponse
    plan: PlanResponse
    usage: SubscriptionUsage
    features: List[str]
    upgrade_suggestions: List[UpgradeSuggestion] = []


class FeatureUsageLog(BaseModel):
    """Schema for feature usage log entry"""
    date: datetime
    count: int
    metadata: Optional[str] = None


class FeatureUsageDetail(BaseModel):
    """Schema for detailed feature usage"""
    total_usage: int
    recent_usage: List[FeatureUsageLog]


class BillingPeriod(BaseModel):
    """Schema for billing period information"""
    start: datetime
    end: datetime
    days_remaining: int


class UsageStatisticsResponse(BaseModel):
    """Response schema for detailed usage statistics"""
    usage_summary: Dict[str, Any]
    usage_by_feature: Dict[str, FeatureUsageDetail]
    billing_period: BillingPeriod


class FeatureInfo(BaseModel):
    """Schema for feature information"""
    key: str
    name: str
    available: bool


class PlanFeatures(BaseModel):
    """Schema for plan features"""
    plan_name: str
    features: List[FeatureInfo]


class FeaturesByPlanResponse(BaseModel):
    """Response schema for features organized by plan"""
    features_by_plan: Dict[str, PlanFeatures]
    all_features: Dict[str, str]


class FeatureAccessResponse(BaseModel):
    """Response schema for feature access check"""
    feature: str
    has_access: bool
    plan_name: str
    required_plans: Optional[List[str]] = None
    upgrade_message: Optional[str] = None


class SubscriptionUpgradeResponse(BaseModel):
    """Response schema for subscription upgrade"""
    success: bool
    message: str
    subscription: SubscriptionResponse


class SubscriptionCancellationDetails(BaseModel):
    """Schema for cancellation details"""
    cancelled_at: datetime
    active_until: datetime
    reason: str


class SubscriptionCancellationResponse(BaseModel):
    """Response schema for subscription cancellation"""
    success: bool
    message: str
    cancellation: SubscriptionCancellationDetails


class PlansListResponse(BaseModel):
    """Response schema for subscription plans list"""
    plans: List[SubscriptionPlanResponse]
    total: int


# Campaign-specific schemas with tier restrictions
class CampaignCreateRequest(BaseModel):
    """Schema for creating campaigns with tier validation"""
    name: str = Field(..., min_length=1, max_length=200)
    subject: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    template_id: Optional[str] = None
    recipients: List[str] = Field(default_factory=list, description="List of contact IDs")
    
    @validator('name', 'subject')
    def validate_required_fields(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Field cannot be empty')
        return v.strip()


class CampaignSchedule(BaseModel):
    """Schema for scheduling campaigns with timezone support"""
    scheduled_at: datetime = Field(..., description="When to send the campaign")
    timezone: str = Field(default="UTC", description="Timezone for scheduling")
    
    @validator('scheduled_at')
    def validate_future_date(cls, v):
        # Handle both timezone-aware and timezone-naive datetimes
        now = datetime.utcnow()
        if v.tzinfo is not None:
            # If incoming datetime is timezone-aware, make now timezone-aware too
            from datetime import timezone
            now = now.replace(tzinfo=timezone.utc)
        elif v.tzinfo is None and hasattr(v, 'replace'):
            # If incoming datetime is timezone-naive, ensure now is also timezone-naive
            pass
        
        if v <= now:
            raise ValueError('Scheduled time must be in the future')
        return v


class ABTestRequest(BaseModel):
    """Schema for A/B testing requests (Pro+ feature)"""
    test_name: str = Field(..., min_length=1, max_length=200)
    test_type: str = Field(..., description="Type of test: subject_line, content, send_time")
    sample_size_percentage: int = Field(default=20, ge=10, le=50)
    winner_criteria: str = Field(default="open_rate", description="Criteria for selecting winner")
    variations: List[Dict[str, Any]] = Field(..., min_items=2, max_items=10)
    
    @validator('test_type')
    def validate_test_type(cls, v):
        allowed_types = ['subject_line', 'content', 'send_time', 'sender_name']
        if v not in allowed_types:
            raise ValueError(f'Test type must be one of: {", ".join(allowed_types)}')
        return v


class SegmentCreateRequest(BaseModel):
    """Schema for creating contact segments (Pro+ feature)"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    criteria: List[Dict[str, Any]] = Field(..., min_items=1, description="Segment criteria")
    
    @validator('name')
    def validate_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('Segment name is required')
        return v.strip()
