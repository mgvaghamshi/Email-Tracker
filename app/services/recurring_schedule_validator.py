"""
Production-Grade Recurring Schedule Validation Service
Implements RRULE generation and validation similar to Mailchimp/HubSpot
"""

import re
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Dict, Any, Optional, Tuple, Union
from dateutil import rrule
from dateutil.tz import gettz
import pytz
from enum import Enum

from ..core.logging_config import get_logger

logger = get_logger(__name__)


class FrequencyType(str, Enum):
    """Supported recurring frequencies"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class MonthlyType(str, Enum):
    """Monthly recurring types"""
    DAY_OF_MONTH = "day_of_month"  # 15th of each month
    NTH_WEEKDAY = "nth_weekday"    # 2nd Tuesday of each month


class ValidationError:
    """Structured validation error"""
    def __init__(self, field: str, message: str, code: str = ""):
        self.field = field
        self.message = message
        self.code = code

    def to_dict(self):
        return {
            "field": self.field,
            "message": self.message,
            "code": self.code
        }


class RecurringScheduleValidator:
    """
    Production-grade Recurring Schedule Validator with DateTime Normalization
    
    Validates recurring campaign schedules, generates RRULEs, and provides preview dates.
    Includes comprehensive datetime normalization to prevent parsing errors.
    """    # Supported timezones (subset for validation)
    SUPPORTED_TIMEZONES = [
        'UTC', 'US/Eastern', 'US/Central', 'US/Mountain', 'US/Pacific',
        'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Rome',
        'Asia/Tokyo', 'Asia/Shanghai', 'Asia/Kolkata', 'Australia/Sydney'
    ]
    
    # Holiday calendars (simplified - in production use proper holiday library)
    HOLIDAY_REGIONS = ['US', 'UK', 'EU', 'CA', 'AU']
    
    # RRULE frequency mapping
    RRULE_FREQ_MAP = {
        FrequencyType.DAILY: rrule.DAILY,
        FrequencyType.WEEKLY: rrule.WEEKLY,
        FrequencyType.MONTHLY: rrule.MONTHLY
    }
    
    # Weekday mapping for RRULE
    WEEKDAY_MAP = {
        'monday': rrule.MO,
        'tuesday': rrule.TU,
        'wednesday': rrule.WE,
        'thursday': rrule.TH,
        'friday': rrule.FR,
        'saturday': rrule.SA,
        'sunday': rrule.SU
    }

    @classmethod
    def validate_and_generate(
        cls, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate recurring schedule configuration and generate RRULE
        
        Args:
            config: Recurring schedule configuration
            
        Returns:
            Dict containing validation results, normalized config, and RRULE
        """
        validator = cls()
        
        # 0. Normalize datetime values first to prevent parsing errors
        try:
            from ..core.datetime_validators import DateTimeValidatorMixin
            dt_validator = DateTimeValidatorMixin()
            
            # Normalize start_date
            if 'start_date' in config and config['start_date']:
                config['start_date'] = dt_validator.normalize_datetime_fields(config['start_date'])
                
            # Normalize end_date
            if 'end_date' in config and config['end_date']:
                config['end_date'] = dt_validator.normalize_datetime_fields(config['end_date'])
                
        except Exception as e:
            return {
                "is_valid": False,
                "errors": [{"field": "datetime", "message": f"DateTime parsing error: {str(e)}", "code": "DATETIME_PARSE_ERROR"}],
                "warnings": [],
                "normalized_config": None,
                "rrule": None,
                "preview_dates": []
            }
        
        # 1. Validate configuration
        errors, warnings = validator._validate_config(config)
        
        if errors:
            return {
                "is_valid": False,
                "errors": [error.to_dict() for error in errors],
                "warnings": warnings,
                "normalized_config": None,
                "rrule": None,
                "preview_dates": []
            }
        
        # 2. Normalize configuration
        normalized_config = validator._normalize_config(config)
        
        # 3. Generate RRULE
        try:
            rrule_obj, rrule_string = validator._generate_rrule(normalized_config)
            
            # 4. Generate preview dates
            preview_dates = validator._generate_preview_dates(rrule_obj, normalized_config)
            
            # 5. Final validation - ensure at least one valid date
            if not preview_dates:
                return {
                    "is_valid": False,
                    "errors": [ValidationError("schedule", "No valid send dates found with this configuration", "NO_VALID_DATES").to_dict()],
                    "warnings": warnings,
                    "normalized_config": normalized_config,
                    "rrule": None,
                    "preview_dates": []
                }
            
            return {
                "is_valid": True,
                "errors": [],
                "warnings": warnings,
                "normalized_config": normalized_config,
                "rrule": rrule_string,
                "preview_dates": [dt.isoformat() for dt in preview_dates[:10]]  # First 10 dates
            }
            
        except Exception as e:
            logger.error(f"RRULE generation failed: {e}")
            return {
                "is_valid": False,
                "errors": [ValidationError("schedule", f"Schedule generation failed: {str(e)}", "RRULE_ERROR").to_dict()],
                "warnings": warnings,
                "normalized_config": normalized_config,
                "rrule": None,
                "preview_dates": []
            }

    def _validate_config(self, config: Dict[str, Any]) -> Tuple[List[ValidationError], List[str]]:
        """Validate the recurring schedule configuration"""
        errors = []
        warnings = []
        
        # Required fields
        if not config.get('frequency'):
            errors.append(ValidationError("frequency", "Frequency is required", "REQUIRED"))
        
        if not config.get('time'):
            errors.append(ValidationError("time", "Send time is required", "REQUIRED"))
        
        if not config.get('start_date'):
            errors.append(ValidationError("start_date", "Start date is required", "REQUIRED"))
        
        # Validate frequency
        if config.get('frequency') and config['frequency'] not in [f.value for f in FrequencyType]:
            errors.append(ValidationError("frequency", "Invalid frequency type", "INVALID_VALUE"))
        
        # Validate dates
        start_date_errors = self._validate_start_date(config.get('start_date'))
        errors.extend(start_date_errors)
        
        end_date_errors, end_date_warnings = self._validate_end_date(
            config.get('start_date'), 
            config.get('end_date')
        )
        errors.extend(end_date_errors)
        warnings.extend(end_date_warnings)
        
        # Validate occurrence limits
        limit_errors = self._validate_occurrence_limits(config)
        errors.extend(limit_errors)
        
        # Validate time format
        time_errors = self._validate_time(config.get('time'))
        errors.extend(time_errors)
        
        # Validate timezone
        tz_errors = self._validate_timezone(config.get('timezone', 'UTC'))
        errors.extend(tz_errors)
        
        # Frequency-specific validation
        freq_errors, freq_warnings = self._validate_frequency_specific(config)
        errors.extend(freq_errors)
        warnings.extend(freq_warnings)
        
        return errors, warnings

    def _validate_start_date(self, start_date: Optional[Union[str, datetime]]) -> List[ValidationError]:
        """Validate start date"""
        errors = []
        
        if not start_date:
            return errors
        
        try:
            # Handle both string and datetime inputs (after normalization)
            if isinstance(start_date, datetime):
                parsed_date = start_date
            elif isinstance(start_date, str):
                # Handle both YYYY-MM-DD and full ISO formats
                if len(start_date) == 10 and start_date.count('-') == 2:
                    # YYYY-MM-DD format - add default time
                    parsed_date = datetime.fromisoformat(f"{start_date}T00:00:00")
                else:
                    # Full ISO format
                    parsed_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                raise ValueError(f"Unsupported start_date type: {type(start_date)}")
            
            # Start date must be today or in the future
            today = datetime.now(dt_timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            if parsed_date.replace(tzinfo=dt_timezone.utc) < today:
                errors.append(ValidationError(
                    "start_date", 
                    "Start date must be today or in the future", 
                    "PAST_DATE"
                ))
                
        except (ValueError, TypeError) as e:
            errors.append(ValidationError(
                "start_date", 
                "Invalid start date format. Use YYYY-MM-DD", 
                "INVALID_FORMAT"
            ))
        
        return errors

    def _validate_end_date(
        self, 
        start_date: Optional[Union[str, datetime]], 
        end_date: Optional[Union[str, datetime]]
    ) -> Tuple[List[ValidationError], List[str]]:
        """Validate end date"""
        errors = []
        warnings = []
        
        if not end_date or not start_date:
            return errors, warnings
        
        try:
            # Handle both string and datetime inputs for start_date
            if isinstance(start_date, datetime):
                start_dt = start_date
            elif isinstance(start_date, str):
                if len(start_date) == 10 and start_date.count('-') == 2:
                    start_dt = datetime.fromisoformat(f"{start_date}T00:00:00")
                else:
                    start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            else:
                raise ValueError(f"Unsupported start_date type: {type(start_date)}")
            
            # Handle both string and datetime inputs for end_date
            if isinstance(end_date, datetime):
                end_dt = end_date
            elif isinstance(end_date, str):
                if len(end_date) == 10 and end_date.count('-') == 2:
                    end_dt = datetime.fromisoformat(f"{end_date}T23:59:59")  # End of day for comparison
                else:
                    end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            else:
                raise ValueError(f"Unsupported end_date type: {type(end_date)}")
            
            if end_dt <= start_dt:
                errors.append(ValidationError(
                    "end_date", 
                    "End date must be after start date", 
                    "INVALID_RANGE"
                ))
            
            # Warn if end date is very far in the future
            if (end_dt - start_dt).days > 365 * 2:  # More than 2 years
                warnings.append("End date is more than 2 years in the future")
                
        except (ValueError, TypeError):
            errors.append(ValidationError(
                "end_date", 
                "Invalid end date format. Use YYYY-MM-DD", 
                "INVALID_FORMAT"
            ))
        
        return errors, warnings

    def _validate_occurrence_limits(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate occurrence limits - must have either end_date OR max_occurrences"""
        errors = []
        
        has_end_date = bool(config.get('end_date'))
        has_max_occurrences = bool(config.get('max_occurrences'))
        
        if not has_end_date and not has_max_occurrences:
            errors.append(ValidationError(
                "limits", 
                "Must specify either an end date or maximum number of occurrences", 
                "MISSING_LIMIT"
            ))
        
        if has_end_date and has_max_occurrences:
            errors.append(ValidationError(
                "limits", 
                "Cannot specify both end date and maximum occurrences", 
                "CONFLICTING_LIMITS"
            ))
        
        if has_max_occurrences:
            try:
                max_occ = int(config['max_occurrences'])
                if max_occ < 1:
                    errors.append(ValidationError(
                        "max_occurrences", 
                        "Maximum occurrences must be at least 1", 
                        "INVALID_VALUE"
                    ))
                elif max_occ > 1000:
                    errors.append(ValidationError(
                        "max_occurrences", 
                        "Maximum occurrences cannot exceed 1000", 
                        "LIMIT_EXCEEDED"
                    ))
            except (ValueError, TypeError):
                errors.append(ValidationError(
                    "max_occurrences", 
                    "Maximum occurrences must be a valid number", 
                    "INVALID_FORMAT"
                ))
        
        return errors

    def _validate_time(self, time_str: Optional[str]) -> List[ValidationError]:
        """Validate time format (HH:MM)"""
        errors = []
        
        if not time_str:
            return errors
        
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_str):
            errors.append(ValidationError(
                "time", 
                "Time must be in HH:MM format (24-hour)", 
                "INVALID_FORMAT"
            ))
        
        return errors

    def _validate_timezone(self, timezone_str: str) -> List[ValidationError]:
        """Validate timezone"""
        errors = []
        
        try:
            # Try to get timezone using pytz
            pytz.timezone(timezone_str)
        except pytz.exceptions.UnknownTimeZoneError:
            # Fallback validation for common timezones
            if timezone_str not in self.SUPPORTED_TIMEZONES:
                errors.append(ValidationError(
                    "timezone", 
                    f"Unsupported timezone: {timezone_str}", 
                    "INVALID_TIMEZONE"
                ))
        
        return errors

    def _validate_frequency_specific(
        self, 
        config: Dict[str, Any]
    ) -> Tuple[List[ValidationError], List[str]]:
        """Validate frequency-specific configuration"""
        errors = []
        warnings = []
        frequency = config.get('frequency')
        
        if frequency == FrequencyType.DAILY:
            errors.extend(self._validate_daily_config(config))
            
        elif frequency == FrequencyType.WEEKLY:
            errors.extend(self._validate_weekly_config(config))
            
        elif frequency == FrequencyType.MONTHLY:
            month_errors, month_warnings = self._validate_monthly_config(config)
            errors.extend(month_errors)
            warnings.extend(month_warnings)
            
        elif frequency == FrequencyType.CUSTOM:
            errors.extend(self._validate_custom_config(config))
        
        return errors, warnings

    def _validate_daily_config(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate daily frequency configuration"""
        errors = []
        
        interval = config.get('interval', 1)
        try:
            interval = int(interval)
            if interval < 1 or interval > 365:
                errors.append(ValidationError(
                    "interval", 
                    "Daily interval must be between 1 and 365 days", 
                    "INVALID_RANGE"
                ))
        except (ValueError, TypeError):
            errors.append(ValidationError(
                "interval", 
                "Daily interval must be a valid number", 
                "INVALID_FORMAT"
            ))
        
        return errors

    def _validate_weekly_config(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate weekly frequency configuration"""
        errors = []
        
        # Validate interval
        interval = config.get('interval', 1)
        try:
            interval = int(interval)
            if interval < 1 or interval > 52:
                errors.append(ValidationError(
                    "interval", 
                    "Weekly interval must be between 1 and 52 weeks", 
                    "INVALID_RANGE"
                ))
        except (ValueError, TypeError):
            errors.append(ValidationError(
                "interval", 
                "Weekly interval must be a valid number", 
                "INVALID_FORMAT"
            ))
        
        # Validate days of week
        days_of_week = config.get('days_of_week', [])
        if not days_of_week:
            errors.append(ValidationError(
                "days_of_week", 
                "At least one day must be selected for weekly frequency", 
                "REQUIRED"
            ))
        else:
            valid_days = set(self.WEEKDAY_MAP.keys())
            for day in days_of_week:
                if day not in valid_days:
                    errors.append(ValidationError(
                        "days_of_week", 
                        f"Invalid day: {day}", 
                        "INVALID_VALUE"
                    ))
        
        return errors

    def _validate_monthly_config(self, config: Dict[str, Any]) -> Tuple[List[ValidationError], List[str]]:
        """Validate monthly frequency configuration"""
        errors = []
        warnings = []
        
        monthly_type = config.get('monthly_type', MonthlyType.DAY_OF_MONTH)
        
        if monthly_type == MonthlyType.DAY_OF_MONTH:
            day_of_month = config.get('day_of_month')
            if not day_of_month:
                errors.append(ValidationError(
                    "day_of_month", 
                    "Day of month is required", 
                    "REQUIRED"
                ))
            else:
                try:
                    day = int(day_of_month)
                    if day < 1 or day > 28:
                        if day > 28:
                            warnings.append(
                                f"Day {day} will fallback to the last day of months "
                                "with fewer days (Feb: 28/29, Apr/Jun/Sep/Nov: 30)"
                            )
                        else:
                            errors.append(ValidationError(
                                "day_of_month", 
                                "Day of month must be between 1 and 31", 
                                "INVALID_RANGE"
                            ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        "day_of_month", 
                        "Day of month must be a valid number", 
                        "INVALID_FORMAT"
                    ))
        
        elif monthly_type == MonthlyType.NTH_WEEKDAY:
            week_number = config.get('week_number')
            weekday = config.get('weekday')
            
            if not week_number:
                errors.append(ValidationError(
                    "week_number", 
                    "Week number is required for nth weekday", 
                    "REQUIRED"
                ))
            else:
                try:
                    week = int(week_number)
                    if week < 1 or week > 5:  # 1st, 2nd, 3rd, 4th, last
                        errors.append(ValidationError(
                            "week_number", 
                            "Week number must be between 1 and 5 (5 = last)", 
                            "INVALID_RANGE"
                        ))
                except (ValueError, TypeError):
                    errors.append(ValidationError(
                        "week_number", 
                        "Week number must be a valid number", 
                        "INVALID_FORMAT"
                    ))
            
            if not weekday or weekday not in self.WEEKDAY_MAP:
                errors.append(ValidationError(
                    "weekday", 
                    "Valid weekday is required for nth weekday", 
                    "REQUIRED"
                ))
        
        return errors, warnings

    def _validate_custom_config(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate custom frequency configuration"""
        errors = []
        
        custom_rrule = config.get('custom_rrule')
        if not custom_rrule:
            errors.append(ValidationError(
                "custom_rrule", 
                "Custom RRULE is required for custom frequency", 
                "REQUIRED"
            ))
        else:
            # Validate RRULE format
            try:
                rrule.rrulestr(custom_rrule)
            except (ValueError, TypeError) as e:
                errors.append(ValidationError(
                    "custom_rrule", 
                    f"Invalid RRULE format: {str(e)}", 
                    "INVALID_RRULE"
                ))
        
        return errors

    def _normalize_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize configuration values"""
        normalized = config.copy()
        
        # Normalize timezone
        if 'timezone' not in normalized:
            normalized['timezone'] = 'UTC'
        
        # Normalize intervals
        if 'interval' not in normalized:
            normalized['interval'] = 1
        else:
            normalized['interval'] = int(normalized['interval'])
        
        # Normalize boolean values
        normalized['skip_weekends'] = bool(normalized.get('skip_weekends', False))
        normalized['skip_holidays'] = bool(normalized.get('skip_holidays', False))
        
        # Normalize monthly type
        if normalized.get('frequency') == FrequencyType.MONTHLY:
            if 'monthly_type' not in normalized:
                normalized['monthly_type'] = MonthlyType.DAY_OF_MONTH
        
        # Normalize day of month (handle edge cases)
        if normalized.get('day_of_month'):
            day = int(normalized['day_of_month'])
            if day > 28:
                # Will be handled during RRULE generation with fallback logic
                normalized['day_of_month'] = day
        
        return normalized

    def _generate_rrule(self, config: Dict[str, Any]) -> Tuple[rrule.rrule, str]:
        """Generate RRULE object and string from normalized config"""
        frequency = config['frequency']
        
        # Handle both datetime objects and strings for start_date (after normalization)
        start_date_raw = config['start_date']
        if isinstance(start_date_raw, datetime):
            start_date = start_date_raw
        elif isinstance(start_date_raw, str):
            start_date = datetime.fromisoformat(start_date_raw.replace('Z', '+00:00'))
        else:
            raise ValueError(f"Unsupported start_date type: {type(start_date_raw)}")
        
        # Base RRULE parameters
        rrule_params = {
            'freq': self.RRULE_FREQ_MAP[frequency],
            'dtstart': start_date,
            'interval': config.get('interval', 1)
        }
        
        # Add end condition - handle both datetime objects and strings
        if config.get('end_date'):
            end_date_raw = config['end_date']
            if isinstance(end_date_raw, datetime):
                end_date = end_date_raw
            elif isinstance(end_date_raw, str):
                end_date = datetime.fromisoformat(end_date_raw.replace('Z', '+00:00'))
            else:
                raise ValueError(f"Unsupported end_date type: {type(end_date_raw)}")
            rrule_params['until'] = end_date
        elif config.get('max_occurrences'):
            rrule_params['count'] = int(config['max_occurrences'])
        
        # Frequency-specific parameters
        if frequency == FrequencyType.WEEKLY:
            days_of_week = config.get('days_of_week', [])
            rrule_params['byweekday'] = [self.WEEKDAY_MAP[day] for day in days_of_week]
        
        elif frequency == FrequencyType.MONTHLY:
            monthly_type = config.get('monthly_type', MonthlyType.DAY_OF_MONTH)
            
            if monthly_type == MonthlyType.DAY_OF_MONTH:
                day_of_month = int(config.get('day_of_month', 1))
                if day_of_month <= 28:
                    rrule_params['bymonthday'] = day_of_month
                else:
                    # For days > 28, use bymonthday with negative values for month-end
                    if day_of_month == 31:
                        rrule_params['bymonthday'] = -1  # Last day of month
                    elif day_of_month == 30:
                        rrule_params['bymonthday'] = [-1, -2]  # Last or second-to-last day
                    else:  # day_of_month == 29
                        rrule_params['bymonthday'] = [-1, -2, -3]  # Last three days of month
            
            elif monthly_type == MonthlyType.NTH_WEEKDAY:
                week_number = int(config.get('week_number', 1))
                weekday = config.get('weekday', 'monday')
                
                rrule_weekday = self.WEEKDAY_MAP[weekday]
                if week_number == 5:  # Last occurrence
                    rrule_params['byweekday'] = rrule_weekday(-1)
                else:
                    rrule_params['byweekday'] = rrule_weekday(week_number)
        
        elif frequency == FrequencyType.CUSTOM:
            # For custom, parse the provided RRULE
            custom_rrule = config.get('custom_rrule')
            return rrule.rrulestr(custom_rrule), custom_rrule
        
        # Create RRULE object
        rrule_obj = rrule.rrule(**rrule_params)
        
        # Generate RRULE string
        rrule_string = str(rrule_obj).replace('\\n', '')
        
        return rrule_obj, rrule_string

    def _generate_preview_dates(
        self, 
        rrule_obj: rrule.rrule, 
        config: Dict[str, Any], 
        max_preview: int = 20
    ) -> List[datetime]:
        """Generate preview dates with time and filtering applied"""
        preview_dates = []
        send_time = config.get('time', '09:00')
        timezone_str = config.get('timezone', 'UTC')
        skip_weekends = config.get('skip_weekends', False)
        
        # Parse time
        hour, minute = map(int, send_time.split(':'))
        
        # Get timezone
        try:
            tz = pytz.timezone(timezone_str)
        except:
            tz = pytz.UTC
        
        # Generate dates
        count = 0
        for dt in rrule_obj:
            if count >= max_preview:
                break
            
            # Apply time
            scheduled_dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Apply timezone
            if scheduled_dt.tzinfo is None:
                scheduled_dt = tz.localize(scheduled_dt)
            
            # Apply filters
            if skip_weekends and scheduled_dt.weekday() >= 5:  # Saturday = 5, Sunday = 6
                continue
            
            # TODO: Add holiday filtering based on region
            
            preview_dates.append(scheduled_dt)
            count += 1
        
        return preview_dates
