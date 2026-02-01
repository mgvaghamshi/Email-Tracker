"""
Recurring Campaign API endpoints - Professional SaaS implementation
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from ...dependencies import get_db
from ...auth.jwt_auth import get_current_user_from_jwt
from ...auth.subscription_auth import require_feature, require_plan
from ...database.user_models import User
from ...database.recurring_models import RecurringStatus
from ...services.recurring_campaign_service import RecurringCampaignService
from ...schemas.recurring_campaigns import (
    RecurringCampaignCreate,
    RecurringCampaignUpdate,
    RecurringCampaignResponse,
    RecurringCampaignListResponse,
    RecurringOccurrenceResponse,
    RecurringOccurrenceListResponse,
    RecurringCampaignStatusUpdate,
    RecurringSchedulePreview,
    RecurringCampaignAnalytics,
    RecurringFrequencyOption
)
from ...core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/recurring-campaigns", tags=["Recurring Campaigns"])


@router.get("/frequency-options", summary="Get available frequency options")
async def get_frequency_options(
    current_user: User = Depends(get_current_user_from_jwt)
):
    """Get available recurring frequency options based on user's subscription tier"""
    
    # Basic options available to all Pro+ users
    options = [
        RecurringFrequencyOption(
            value="daily",
            label="Daily",
            description="Send every day at the specified time",
            requires_pro=True
        ),
        RecurringFrequencyOption(
            value="weekly",
            label="Weekly",
            description="Send once per week on selected days",
            requires_pro=True
        ),
        RecurringFrequencyOption(
            value="biweekly",
            label="Bi-weekly",
            description="Send every two weeks",
            requires_pro=True
        ),
        RecurringFrequencyOption(
            value="monthly",
            label="Monthly",
            description="Send once per month",
            requires_pro=True
        ),
        RecurringFrequencyOption(
            value="quarterly",
            label="Quarterly",
            description="Send every 3 months",
            requires_enterprise=True
        ),
        RecurringFrequencyOption(
            value="yearly",
            label="Yearly",
            description="Send once per year",
            requires_enterprise=True
        ),
        RecurringFrequencyOption(
            value="custom",
            label="Custom Interval",
            description="Send at custom day intervals",
            requires_enterprise=True
        )
    ]
    
    return {"options": options}


@router.post("/", response_model=RecurringCampaignResponse, summary="Create recurring campaign")
@require_feature('recurring_campaigns', error_message="Recurring campaigns require Pro plan or higher. Upgrade to create automated email sequences.")
async def create_recurring_campaign(
    campaign_data: RecurringCampaignCreate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """
    Create a new recurring campaign
    
    **Tier Requirements:**
    - Pro: Basic recurring (daily, weekly, biweekly, monthly)
    - Enterprise: Advanced recurring (quarterly, yearly, custom intervals)
    """
    try:
        service = RecurringCampaignService(db)
        
        # Convert Pydantic model to dict for service
        campaign_dict = campaign_data.model_dump()
        
        # Map subject_template from API to subject in database
        if 'subject_template' in campaign_dict:
            campaign_dict['subject'] = campaign_dict.pop('subject_template')
        
        # Extract and process schedule configuration
        schedule_config = campaign_dict.pop('schedule_config')
        campaign_dict.update(schedule_config)
        
        # Convert weekdays enum to strings
        if campaign_dict.get('send_on_weekdays'):
            campaign_dict['send_on_weekdays'] = [
                day.value for day in campaign_dict['send_on_weekdays']
            ]
        
        recurring_campaign = await service.create_recurring_campaign(
            user_id=current_user.id,
            campaign_data=campaign_dict
        )
        
        logger.info(f"Created recurring campaign {recurring_campaign.id} for user {current_user.id}")
        
        return RecurringCampaignResponse.from_orm(recurring_campaign)
        
    except Exception as e:
        logger.error(f"Failed to create recurring campaign for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create recurring campaign: {str(e)}"
        )


@router.get("/", response_model=RecurringCampaignListResponse, summary="List recurring campaigns")
@require_feature('recurring_campaigns')
async def list_recurring_campaigns(
    status: Optional[RecurringStatus] = Query(None, description="Filter by campaign status"),
    skip: int = Query(0, ge=0, description="Number of campaigns to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of campaigns to return"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """List user's recurring campaigns with filtering and pagination"""
    
    try:
        service = RecurringCampaignService(db)
        campaigns, total = service.get_recurring_campaigns(
            user_id=current_user.id,
            status=status,
            skip=skip,
            limit=limit
        )
        
        campaign_responses = [RecurringCampaignResponse.from_orm(campaign) for campaign in campaigns]
        
        return RecurringCampaignListResponse(
            data=campaign_responses,
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to list recurring campaigns for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve recurring campaigns"
        )


@router.get("/{campaign_id}", response_model=RecurringCampaignResponse, summary="Get recurring campaign")
@require_feature('recurring_campaigns')
async def get_recurring_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get a specific recurring campaign by ID"""
    
    from ...database.recurring_models import RecurringCampaign
    from sqlalchemy import and_
    
    campaign = db.query(RecurringCampaign).filter(
        and_(
            RecurringCampaign.id == campaign_id,
            RecurringCampaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="Recurring campaign not found"
        )
    
    return RecurringCampaignResponse.from_orm(campaign)


@router.put("/{campaign_id}", response_model=RecurringCampaignResponse, summary="Update recurring campaign")
@require_feature('recurring_campaigns')
async def update_recurring_campaign(
    campaign_id: str,
    update_data: RecurringCampaignUpdate,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Update a recurring campaign (limited updates allowed for active campaigns)"""
    
    from ...database.recurring_models import RecurringCampaign
    from sqlalchemy import and_
    
    campaign = db.query(RecurringCampaign).filter(
        and_(
            RecurringCampaign.id == campaign_id,
            RecurringCampaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="Recurring campaign not found"
        )
    
    # Restrict updates for active campaigns
    if campaign.status == RecurringStatus.ACTIVE:
        restricted_fields = ['frequency', 'custom_interval_days', 'send_on_weekdays', 'send_time', 'start_date']
        update_dict = update_data.dict(exclude_unset=True)
        
        for field in restricted_fields:
            if field in update_dict:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot modify {field} on active recurring campaign. Pause campaign first."
                )
    
    # Apply updates
    update_dict = update_data.dict(exclude_unset=True)
    for field, value in update_dict.items():
        if hasattr(campaign, field):
            setattr(campaign, field, value)
    
    campaign.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(campaign)
    
    logger.info(f"Updated recurring campaign {campaign_id}")
    
    return RecurringCampaignResponse.from_orm(campaign)


@router.post("/{campaign_id}/activate", summary="Activate recurring campaign")
@require_feature('recurring_campaigns')
async def activate_recurring_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Activate a draft recurring campaign to start sending"""
    
    try:
        service = RecurringCampaignService(db)
        success = await service.activate_recurring_campaign(campaign_id, current_user.id)
        
        if not success:
            # Get the campaign to check its current status
            from ...database.recurring_models import RecurringCampaign
            from sqlalchemy import and_
            
            campaign = db.query(RecurringCampaign).filter(
                and_(
                    RecurringCampaign.id == campaign_id,
                    RecurringCampaign.user_id == current_user.id
                )
            ).first()
            
            if not campaign:
                raise HTTPException(
                    status_code=404,
                    detail="Recurring campaign not found"
                )
            
            # Check validation errors to provide specific feedback
            validation_errors = await service._validate_campaign_for_activation(campaign)
            if validation_errors:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot activate campaign: {'; '.join(validation_errors)}"
                )
            
            raise HTTPException(
                status_code=400,
                detail="Failed to activate recurring campaign. Check campaign configuration."
            )
        
        return {"message": "Recurring campaign activated successfully", "campaign_id": campaign_id}
        
    except HTTPException:
        # Re-raise HTTP exceptions to preserve status codes and messages
        raise
    except Exception as e:
        logger.error(f"Failed to activate recurring campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate recurring campaign: {str(e)}"
        )


@router.post("/{campaign_id}/pause", summary="Pause recurring campaign")
@require_feature('recurring_campaigns')
async def pause_recurring_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Pause an active recurring campaign"""
    
    try:
        service = RecurringCampaignService(db)
        success = await service.pause_recurring_campaign(campaign_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Recurring campaign not found"
            )
        
        return {"message": "Recurring campaign paused successfully", "campaign_id": campaign_id}
        
    except Exception as e:
        logger.error(f"Failed to pause recurring campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to pause recurring campaign"
        )


@router.post("/{campaign_id}/resume", summary="Resume recurring campaign")
@require_feature('recurring_campaigns')
async def resume_recurring_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Resume a paused recurring campaign"""
    
    try:
        service = RecurringCampaignService(db)
        success = await service.resume_recurring_campaign(campaign_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Cannot resume recurring campaign. Campaign not found or not paused."
            )
        
        return {"message": "Recurring campaign resumed successfully", "campaign_id": campaign_id}
        
    except Exception as e:
        logger.error(f"Failed to resume recurring campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to resume recurring campaign"
        )


@router.post("/{campaign_id}/cancel", summary="Cancel recurring campaign")
@require_feature('recurring_campaigns')
async def cancel_recurring_campaign(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Cancel a recurring campaign (cannot be undone)"""
    
    try:
        service = RecurringCampaignService(db)
        success = await service.cancel_recurring_campaign(campaign_id, current_user.id)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Recurring campaign not found"
            )
        
        return {"message": "Recurring campaign cancelled successfully", "campaign_id": campaign_id}
        
    except Exception as e:
        logger.error(f"Failed to cancel recurring campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to cancel recurring campaign"
        )


@router.get("/{campaign_id}/occurrences", response_model=RecurringOccurrenceListResponse, summary="Get campaign occurrences")
@require_feature('recurring_campaigns')
async def get_campaign_occurrences(
    campaign_id: str,
    skip: int = Query(0, ge=0, description="Number of occurrences to skip"),
    limit: int = Query(50, ge=1, le=100, description="Number of occurrences to return"),
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get occurrences (individual sends) for a recurring campaign"""
    
    try:
        service = RecurringCampaignService(db)
        occurrences, total = service.get_campaign_occurrences(
            campaign_id=campaign_id,
            user_id=current_user.id,
            skip=skip,
            limit=limit
        )
        
        occurrence_responses = [RecurringOccurrenceResponse.from_orm(occ) for occ in occurrences]
        
        return RecurringOccurrenceListResponse(
            data=occurrence_responses,
            total=total,
            page=(skip // limit) + 1,
            limit=limit
        )
        
    except Exception as e:
        logger.error(f"Failed to get occurrences for campaign {campaign_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve campaign occurrences"
        )


@router.post("/preview-schedule", response_model=RecurringSchedulePreview, summary="Preview recurring schedule")
@require_feature('recurring_campaigns')
async def preview_recurring_schedule(
    schedule_data: RecurringCampaignCreate,
    current_user: User = Depends(get_current_user_from_jwt)
):
    """Preview the schedule for a recurring campaign configuration"""
    
    try:
        from ...database.recurring_models import RecurringCampaign
        
        # Create temporary campaign object for preview
        temp_campaign = RecurringCampaign(
            **schedule_data.model_dump()['schedule_config'],
            start_date=schedule_data.start_date,
            end_date=schedule_data.end_date,
            max_occurrences=schedule_data.max_occurrences
        )
        
        # Generate preview dates
        preview_dates = []
        current_date = temp_campaign.start_date
        count = 0
        max_preview = 20  # Limit preview to 20 dates
        
        while (
            count < max_preview and
            (not temp_campaign.max_occurrences or count < temp_campaign.max_occurrences) and
            (not temp_campaign.end_date or current_date <= temp_campaign.end_date)
        ):
            if temp_campaign.should_send_today(current_date):
                preview_dates.append(current_date)
                count += 1
            
            next_date = temp_campaign.calculate_next_send_date(current_date)
            if not next_date or next_date <= current_date:
                break
            current_date = next_date
        
        # Calculate total occurrences estimate
        estimated_total = temp_campaign.max_occurrences or len(preview_dates)
        
        # Estimate completion date
        estimated_completion = None
        if preview_dates and (temp_campaign.max_occurrences or temp_campaign.end_date):
            if temp_campaign.end_date:
                estimated_completion = temp_campaign.end_date
            elif len(preview_dates) >= (temp_campaign.max_occurrences or 0):
                estimated_completion = preview_dates[-1]
        
        # Generate warnings
        warnings = []
        if not preview_dates:
            warnings.append("No send dates found with current configuration")
        
        if temp_campaign.skip_weekends and temp_campaign.frequency == "daily":
            warnings.append("Daily frequency with weekend skipping will only send on weekdays")
        
        return RecurringSchedulePreview(
            next_send_dates=preview_dates,
            total_occurrences=estimated_total,
            estimated_completion=estimated_completion,
            warnings=warnings
        )
        
    except Exception as e:
        logger.error(f"Failed to preview recurring schedule: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate schedule preview"
        )


@router.get("/{campaign_id}/analytics", response_model=RecurringCampaignAnalytics, summary="Get campaign analytics")
@require_feature('recurring_campaigns')
async def get_recurring_campaign_analytics(
    campaign_id: str,
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    """Get comprehensive analytics for a recurring campaign"""
    
    from ...database.recurring_models import RecurringCampaign, RecurringCampaignOccurrence
    from sqlalchemy import and_, func
    
    # Get campaign
    campaign = db.query(RecurringCampaign).filter(
        and_(
            RecurringCampaign.id == campaign_id,
            RecurringCampaign.user_id == current_user.id
        )
    ).first()
    
    if not campaign:
        raise HTTPException(
            status_code=404,
            detail="Recurring campaign not found"
        )
    
    # Get aggregated metrics from occurrences
    metrics = db.query(
        func.count(RecurringCampaignOccurrence.id).label('total_occurrences'),
        func.sum(func.case([(RecurringCampaignOccurrence.status == 'sent', 1)], else_=0)).label('completed'),
        func.sum(func.case([(RecurringCampaignOccurrence.status == 'failed', 1)], else_=0)).label('failed'),
        func.sum(RecurringCampaignOccurrence.recipients_count).label('total_recipients'),
        func.sum(RecurringCampaignOccurrence.emails_sent).label('total_sent'),
        func.sum(RecurringCampaignOccurrence.emails_delivered).label('total_delivered'),
        func.sum(RecurringCampaignOccurrence.emails_opened).label('total_opened'),
        func.sum(RecurringCampaignOccurrence.emails_clicked).label('total_clicked'),
    ).filter(
        RecurringCampaignOccurrence.recurring_campaign_id == campaign_id
    ).first()
    
    # Calculate average rates
    total_delivered = metrics.total_delivered or 0
    avg_delivery_rate = (total_delivered / (metrics.total_sent or 1)) * 100 if metrics.total_sent else 0
    avg_open_rate = ((metrics.total_opened or 0) / max(total_delivered, 1)) * 100
    avg_click_rate = ((metrics.total_clicked or 0) / max(total_delivered, 1)) * 100
    
    # Get performance trend (last 30 occurrences)
    recent_occurrences = db.query(RecurringCampaignOccurrence).filter(
        RecurringCampaignOccurrence.recurring_campaign_id == campaign_id
    ).order_by(RecurringCampaignOccurrence.scheduled_at.desc()).limit(30).all()
    
    performance_trend = []
    for occ in reversed(recent_occurrences):  # Reverse to get chronological order
        if occ.emails_delivered > 0:
            open_rate = (occ.emails_opened / occ.emails_delivered) * 100
            click_rate = (occ.emails_clicked / occ.emails_delivered) * 100
        else:
            open_rate = click_rate = 0
        
        performance_trend.append({
            "date": occ.scheduled_at.isoformat(),
            "sequence": occ.sequence_number,
            "recipients": occ.recipients_count,
            "sent": occ.emails_sent,
            "delivered": occ.emails_delivered,
            "opened": occ.emails_opened,
            "clicked": occ.emails_clicked,
            "open_rate": round(open_rate, 2),
            "click_rate": round(click_rate, 2)
        })
    
    return RecurringCampaignAnalytics(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        total_occurrences=metrics.total_occurrences or 0,
        completed_occurrences=metrics.completed or 0,
        failed_occurrences=metrics.failed or 0,
        total_recipients=metrics.total_recipients or 0,
        total_sent=metrics.total_sent or 0,
        total_delivered=metrics.total_delivered or 0,
        total_opened=metrics.total_opened or 0,
        total_clicked=metrics.total_clicked or 0,
        avg_delivery_rate=round(avg_delivery_rate, 2),
        avg_open_rate=round(avg_open_rate, 2),
        avg_click_rate=round(avg_click_rate, 2),
        performance_trend=performance_trend,
        status=campaign.status,
        is_active=campaign.is_active,
        next_send_at=campaign.next_send_at
    )
