"""
Subscription management API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...database.subscription_models import (
    SubscriptionPlan, 
    UserSubscription, 
    FeatureUsageLog,
    create_default_plans,
    assign_default_subscription
)
from ...database.user_models import User
from ...services.subscription_service import FeatureAccessService, get_user_access_service
from ...schemas import subscriptions as schemas

router = APIRouter(prefix="/subscription", tags=["subscription"])


@router.get("/plans", summary="Get all available subscription plans")
async def get_subscription_plans(
    db: Session = Depends(get_db)
):
    """
    Get all available subscription plans with features and pricing.
    """
    # Ensure default plans exist
    create_default_plans(db)
    
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.sort_order).all()
    
    plan_data = []
    for plan in plans:
        plan_info = {
            "id": plan.id,
            "name": plan.name,
            "display_name": plan.display_name,
            "description": plan.description,
            "price": plan.price,
            "billing_interval": plan.billing_interval,
            "display_price": plan.get_display_price(),
            "is_popular": plan.is_popular,
            "limits": {
                "max_campaigns": plan.max_campaigns,
                "max_recipients_per_campaign": plan.max_recipients_per_campaign,
                "max_monthly_emails": plan.max_monthly_emails,
                "max_templates": plan.max_templates,
                "max_contacts": plan.max_contacts
            },
            "features": plan.features_list,
            "sort_order": plan.sort_order
        }
        plan_data.append(plan_info)
    
    return {
        "plans": plan_data,
        "total": len(plan_data)
    }


@router.get("/current", summary="Get current user subscription")
async def get_current_subscription(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get the current user's subscription details including usage stats.
    """
    access_service = get_user_access_service(current_user.id, db)
    
    # Get usage stats
    usage_stats = access_service.get_usage_stats()
    
    # Get upgrade suggestions
    upgrade_suggestions = access_service.get_upgrade_suggestions()
    
    if not access_service.user_subscription:
        # Create default subscription if none exists
        subscription = assign_default_subscription(current_user.id, db)
        access_service = get_user_access_service(current_user.id, db)
        usage_stats = access_service.get_usage_stats()
    
    subscription = access_service.user_subscription
    plan = access_service.plan
    
    return {
        "subscription": {
            "id": subscription.id,
            "status": subscription.status,
            "current_period_start": subscription.current_period_start.isoformat(),
            "current_period_end": subscription.current_period_end.isoformat(),
            "is_trial": subscription.is_trial(),
            "days_until_renewal": subscription.days_until_renewal(),
            "cancel_at_period_end": subscription.cancel_at_period_end
        },
        "plan": {
            "id": plan.id,
            "name": plan.name,
            "display_name": plan.display_name,
            "description": plan.description,
            "price": plan.price,
            "billing_interval": plan.billing_interval,
            "display_price": plan.get_display_price()
        },
        "usage": usage_stats.get('usage', {}),
        "features": usage_stats.get('features', []),
        "upgrade_suggestions": upgrade_suggestions
    }


@router.get("/usage", summary="Get detailed usage statistics")
async def get_usage_statistics(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Get detailed usage statistics for the current user.
    """
    access_service = get_user_access_service(current_user.id, db)
    
    if not access_service.user_subscription:
        raise HTTPException(status_code=404, detail="No subscription found")
    
    # Get recent usage logs
    recent_usage = db.query(FeatureUsageLog).filter(
        FeatureUsageLog.user_id == current_user.id,
        FeatureUsageLog.usage_date >= datetime.utcnow() - timedelta(days=30)
    ).order_by(FeatureUsageLog.usage_date.desc()).limit(100).all()
    
    usage_by_feature = {}
    for log in recent_usage:
        if log.feature_name not in usage_by_feature:
            usage_by_feature[log.feature_name] = {
                'total_usage': 0,
                'recent_usage': []
            }
        
        usage_by_feature[log.feature_name]['total_usage'] += log.usage_count
        usage_by_feature[log.feature_name]['recent_usage'].append({
            'date': log.usage_date.isoformat(),
            'count': log.usage_count,
            'metadata': log.metadata
        })
    
    return {
        "usage_summary": access_service.get_usage_stats(),
        "usage_by_feature": usage_by_feature,
        "billing_period": {
            "start": access_service.user_subscription.current_period_start.isoformat(),
            "end": access_service.user_subscription.current_period_end.isoformat(),
            "days_remaining": access_service.user_subscription.days_until_renewal()
        }
    }


@router.post("/upgrade", summary="Upgrade subscription plan")
async def upgrade_subscription(
    upgrade_data: schemas.SubscriptionUpgrade,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Upgrade user's subscription to a new plan.
    
    Note: This is a simplified implementation. In production, you would
    integrate with a payment processor like Stripe.
    """
    # Get target plan
    target_plan = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.id == upgrade_data.plan_id,
        SubscriptionPlan.is_active == True
    ).first()
    
    if not target_plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Get or create user subscription
    access_service = get_user_access_service(current_user.id, db)
    
    if not access_service.user_subscription:
        subscription = assign_default_subscription(current_user.id, db)
    else:
        subscription = access_service.user_subscription
    
    # Validate upgrade (can't downgrade for now)
    current_plan_order = subscription.plan.sort_order
    target_plan_order = target_plan.sort_order
    
    if target_plan_order <= current_plan_order and target_plan.name != 'enterprise':
        raise HTTPException(
            status_code=400, 
            detail="Cannot downgrade plans. Please contact support for downgrades."
        )
    
    # Update subscription
    old_plan_name = subscription.plan.display_name
    subscription.plan_id = target_plan.id
    subscription.status = 'active'
    
    # Reset billing period
    now = datetime.utcnow()
    subscription.current_period_start = now
    
    if target_plan.billing_interval == 'yearly':
        subscription.current_period_end = now + timedelta(days=365)
    else:
        subscription.current_period_end = now + timedelta(days=30)
    
    subscription.updated_at = now
    
    # Reset usage counters if upgrading
    subscription.campaigns_used = 0
    subscription.emails_sent_this_month = 0
    subscription.templates_used = 0
    subscription.contacts_count = 0
    
    try:
        db.commit()
        
        # Log the upgrade
        access_service._log_usage(
            'subscription_upgrade',
            metadata={
                'from_plan': old_plan_name,
                'to_plan': target_plan.display_name,
                'upgrade_type': upgrade_data.upgrade_type or 'manual'
            }
        )
        
        return {
            "success": True,
            "message": f"Successfully upgraded from {old_plan_name} to {target_plan.display_name}",
            "subscription": {
                "id": subscription.id,
                "plan_name": target_plan.display_name,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start.isoformat(),
                "current_period_end": subscription.current_period_end.isoformat()
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upgrade subscription: {str(e)}"
        )


@router.post("/cancel", summary="Cancel subscription")
async def cancel_subscription(
    cancellation_data: schemas.SubscriptionCancellation,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Cancel user's subscription. The subscription remains active until the end
    of the current billing period.
    """
    access_service = get_user_access_service(current_user.id, db)
    
    if not access_service.user_subscription:
        raise HTTPException(status_code=404, detail="No active subscription found")
    
    subscription = access_service.user_subscription
    
    if subscription.status == 'cancelled':
        raise HTTPException(status_code=400, detail="Subscription is already cancelled")
    
    # Mark for cancellation at period end
    subscription.cancel_at_period_end = True
    subscription.cancelled_at = datetime.utcnow()
    subscription.cancellation_reason = cancellation_data.reason
    subscription.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        
        # Log the cancellation
        access_service._log_usage(
            'subscription_cancel',
            metadata={
                'reason': cancellation_data.reason,
                'cancel_immediately': cancellation_data.cancel_immediately
            }
        )
        
        return {
            "success": True,
            "message": "Subscription cancelled successfully",
            "cancellation": {
                "cancelled_at": subscription.cancelled_at.isoformat(),
                "active_until": subscription.current_period_end.isoformat(),
                "reason": subscription.cancellation_reason
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel subscription: {str(e)}"
        )


@router.get("/features", summary="Get available features by plan")
async def get_features_by_plan(
    db: Session = Depends(get_db)
):
    """
    Get all available features organized by subscription plan.
    """
    from ...database.subscription_models import SUBSCRIPTION_FEATURES
    
    plans = db.query(SubscriptionPlan).filter(
        SubscriptionPlan.is_active == True
    ).order_by(SubscriptionPlan.sort_order).all()
    
    features_by_plan = {}
    
    for plan in plans:
        plan_features = []
        for feature_key in plan.features_list:
            feature_info = {
                "key": feature_key,
                "name": SUBSCRIPTION_FEATURES.get(feature_key, feature_key),
                "available": True
            }
            plan_features.append(feature_info)
        
        features_by_plan[plan.name] = {
            "plan_name": plan.display_name,
            "features": plan_features
        }
    
    return {
        "features_by_plan": features_by_plan,
        "all_features": SUBSCRIPTION_FEATURES
    }


@router.get("/access-check/{feature}", summary="Check feature access")
async def check_feature_access(
    feature: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Check if the current user has access to a specific feature.
    """
    access_service = get_user_access_service(current_user.id, db)
    
    has_access = access_service.has_feature(feature)
    
    response = {
        "feature": feature,
        "has_access": has_access,
        "plan_name": access_service.get_plan_display_name()
    }
    
    if not has_access:
        # Get required plan for this feature
        required_plans = []
        plans = db.query(SubscriptionPlan).filter(
            SubscriptionPlan.is_active == True
        ).all()
        
        for plan in plans:
            if plan.has_feature(feature):
                required_plans.append(plan.display_name)
        
        response["required_plans"] = required_plans
        response["upgrade_message"] = f"Upgrade to {' or '.join(required_plans)} to access {feature}"
    
    return response


# Initialize default plans on startup
@router.on_event("startup")
async def initialize_subscription_plans():
    """Initialize default subscription plans"""
    from ...dependencies import get_db
    
    # This will be called when the router is included
    # In a real application, you might want to do this in a startup script
    pass
