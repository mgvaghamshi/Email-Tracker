"""
Global DateTime Validators for EmailTracker Backend

Provides consistent datetime handling across all Pydantic models.
Prevents datetime_parsing errors by normalizing input formats.
"""

from datetime import datetime, date, time, timezone
from typing import Any, Optional, Union
from pydantic import field_validator
import re


class DateTimeValidatorMixin:
    """
    Mixin class providing consistent datetime validation for Pydantic models.
    
    Usage:
        class MyModel(BaseModel, DateTimeValidatorMixin):
            start_date: datetime
            end_date: Optional[datetime] = None
    """

    @field_validator('start_date', 'end_date', 'created_at', 'updated_at', 'scheduled_at', mode='before')
    @classmethod
    def normalize_datetime_fields(cls, v: Any) -> Optional[datetime]:
        """
        Normalizes datetime inputs to datetime objects.
        
        Handles:
        - ISO datetime strings (2025-08-24T10:00:00Z)
        - Date-only strings (2025-08-24)
        - Date objects
        - Datetime objects
        - None values
        
        Args:
            v: Input value to normalize
            
        Returns:
            Normalized datetime object or None
            
        Raises:
            ValueError: If input cannot be parsed as a valid datetime
        """
        if v is None:
            return None
            
        # Already a datetime object
        if isinstance(v, datetime):
            # Ensure timezone is set (convert to UTC if naive)
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
            
        # Date object without time
        if isinstance(v, date) and not isinstance(v, datetime):
            # Convert to datetime at midnight UTC
            return datetime.combine(v, time.min, tzinfo=timezone.utc)
            
        # String input
        if isinstance(v, str):
            v = v.strip()
            
            # Empty string
            if not v:
                return None
                
            try:
                # Try ISO format first (most common)
                if 'T' in v:
                    # Has time component
                    dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
                    # Ensure UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.astimezone(timezone.utc)
                    
                # Date-only format (YYYY-MM-DD)
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', v):
                    dt = datetime.strptime(v, '%Y-%m-%d')
                    return dt.replace(tzinfo=timezone.utc)
                    
                # Try other common formats
                for fmt in [
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d %H:%M',
                    '%d/%m/%Y',
                    '%m/%d/%Y',
                    '%d-%m-%Y',
                    '%Y/%m/%d'
                ]:
                    try:
                        dt = datetime.strptime(v, fmt)
                        return dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        continue
                        
                # Last resort: try fromisoformat with cleanup
                v_clean = v.replace(' ', 'T')
                if not v_clean.endswith('Z') and '+' not in v_clean and 'T' in v_clean:
                    v_clean += 'Z'
                dt = datetime.fromisoformat(v_clean.replace('Z', '+00:00'))
                return dt.astimezone(timezone.utc)
                
            except (ValueError, TypeError) as e:
                raise ValueError(f"Unable to parse datetime: '{v}'. Expected ISO format (YYYY-MM-DDTHH:MM:SSZ) or date format (YYYY-MM-DD). Error: {e}")
                
        # Unsupported type
        raise ValueError(f"Unsupported datetime type: {type(v)}. Expected string, date, or datetime object.")


def normalize_to_utc_aware(dt: Union[datetime, str]) -> datetime:
    """
    Normalize any datetime input to a timezone-aware UTC datetime.
    
    Args:
        dt: Input datetime (either datetime object or string)
        
    Returns:
        UTC-aware datetime object
        
    Raises:
        ValueError: If input cannot be parsed
    """
    if isinstance(dt, str):
        # Use the mixin's normalization logic
        validator = DateTimeValidatorMixin()
        return validator.normalize_datetime_fields(dt)
    elif isinstance(dt, datetime):
        # If naive, assume UTC
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        # If aware, convert to UTC
        return dt.astimezone(timezone.utc)
    else:
        raise ValueError(f"Unsupported type for datetime normalization: {type(dt)}")


def validate_future_datetime(v: Optional[datetime], field_name: str = 'datetime') -> Optional[datetime]:
    """
    Validates that a datetime is in the future.
    
    Args:
        v: Datetime to validate
        field_name: Name of the field for error messages
        
    Returns:
        The datetime if valid
        
    Raises:
        ValueError: If datetime is in the past
    """
    if v is None:
        return None
        
    now = datetime.now(timezone.utc)
    
    # Ensure we can compare the datetimes properly
    if v.tzinfo is None:
        # If input is naive, assume it's in UTC for comparison
        v_aware = v.replace(tzinfo=timezone.utc)
    else:
        v_aware = v
        
    if v_aware <= now:
        raise ValueError(f"{field_name} must be in the future. Got: {v_aware.isoformat()}, Current time: {now.isoformat()}")
        
    return v


def validate_datetime_range(
    start: Optional[datetime], 
    end: Optional[datetime],
    allow_same: bool = False
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Validates that end datetime is after start datetime.
    
    Args:
        start: Start datetime
        end: End datetime
        allow_same: Whether to allow start and end to be the same
        
    Returns:
        Tuple of (start, end) if valid
        
    Raises:
        ValueError: If end is before start
    """
    if start is None or end is None:
        return start, end
        
    if allow_same:
        if end < start:
            raise ValueError(f"End date ({end.isoformat()}) must be after or equal to start date ({start.isoformat()})")
    else:
        if end <= start:
            raise ValueError(f"End date ({end.isoformat()}) must be after start date ({start.isoformat()})")
            
    return start, end


class RecurringScheduleValidator:
    """
    Specialized validator for recurring schedule configurations.
    """
    
    @staticmethod
    def validate_schedule_config(config: dict) -> dict:
        """
        Validates and normalizes a recurring schedule configuration.
        
        Args:
            config: Raw configuration dictionary
            
        Returns:
            Normalized configuration dictionary
            
        Raises:
            ValueError: If configuration is invalid
        """
        normalized = config.copy()
        
        # Normalize datetime fields
        if 'start_date' in normalized:
            dt_validator = DateTimeValidatorMixin()
            normalized['start_date'] = dt_validator.normalize_datetime_fields(normalized['start_date'])
            
        if 'end_date' in normalized:
            dt_validator = DateTimeValidatorMixin()
            normalized['end_date'] = dt_validator.normalize_datetime_fields(normalized['end_date'])
            
        # Validate future datetime
        if normalized.get('start_date'):
            validate_future_datetime(normalized['start_date'], 'start_date')
            
        # Validate datetime range
        if normalized.get('start_date') and normalized.get('end_date'):
            validate_datetime_range(normalized['start_date'], normalized['end_date'])
            
        # Validate frequency-specific requirements
        frequency = normalized.get('frequency', 'weekly')
        
        if frequency == 'weekly':
            if not normalized.get('days_of_week'):
                raise ValueError("Weekly frequency requires 'days_of_week' to be specified")
                
        elif frequency == 'monthly':
            monthly_type = normalized.get('monthly_type', 'day_of_month')
            if monthly_type == 'day_of_month':
                day_of_month = normalized.get('day_of_month')
                if not day_of_month or not (1 <= day_of_month <= 31):
                    raise ValueError("Monthly day_of_month frequency requires 'day_of_month' between 1-31")
            elif monthly_type == 'nth_weekday':
                if not normalized.get('week_number') or not normalized.get('weekday'):
                    raise ValueError("Monthly nth_weekday frequency requires 'week_number' and 'weekday'")
                    
        elif frequency == 'custom':
            if not normalized.get('custom_rrule'):
                raise ValueError("Custom frequency requires 'custom_rrule' to be specified")
                
        return normalized
