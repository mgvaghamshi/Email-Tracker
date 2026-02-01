"""
Professional time formatting utilities for SaaS applications
Provides human-readable relative time formatting (like GitHub, Slack, Google)
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import pytz


def get_relative_time(timestamp: datetime, reference_time: Optional[datetime] = None) -> str:
    """
    Get human-readable relative time string from datetime object
    
    Args:
        timestamp: The datetime to format
        reference_time: Reference time (defaults to now)
    
    Returns:
        String like "22 minutes ago", "Yesterday", "on Aug 1, 2025"
    """
    if not timestamp:
        return "Unknown"
    
    # Ensure we have timezone-aware datetimes
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    elif reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    
    # Calculate time difference
    delta = reference_time - timestamp
    total_seconds = delta.total_seconds()
    
    # Handle future timestamps
    if total_seconds < 0:
        delta = timestamp - reference_time
        total_seconds = delta.total_seconds()
        return _format_future_time(total_seconds)
    
    return _format_past_time(total_seconds, timestamp)


def _format_past_time(total_seconds: float, timestamp: datetime) -> str:
    """Format past time differences with professional formatting"""
    if total_seconds < 30:  # Less than 30 seconds
        return "Just now"
    
    elif total_seconds < 3600:  # Less than 1 hour
        minutes = int(total_seconds // 60)
        return f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
    
    elif total_seconds < 86400:  # Less than 24 hours
        hours = int(total_seconds // 3600)
        return f"{hours} {'hour' if hours == 1 else 'hours'} ago"
    
    elif total_seconds < 172800:  # Less than 48 hours (2 days)
        return "Yesterday"
    
    elif total_seconds < 604800:  # Less than 7 days
        days = int(total_seconds // 86400)
        return f"{days} {'day' if days == 1 else 'days'} ago"
    
    elif total_seconds < 2592000:  # Less than 30 days
        weeks = int(total_seconds // 604800)
        return f"{weeks} {'week' if weeks == 1 else 'weeks'} ago"
    
    else:  # 30+ days - show date
        return f"on {timestamp.strftime('%b %d, %Y')}"


def _format_future_time(total_seconds: float) -> str:
    """Format future time differences with professional formatting"""
    if total_seconds < 30:  # Less than 30 seconds
        return "in a moment"
    
    elif total_seconds < 3600:  # Less than 1 hour
        minutes = int(total_seconds // 60)
        return f"in {minutes} {'minute' if minutes == 1 else 'minutes'}"
    
    elif total_seconds < 86400:  # Less than 24 hours
        hours = int(total_seconds // 3600)
        return f"in {hours} {'hour' if hours == 1 else 'hours'}"
    
    elif total_seconds < 604800:  # Less than 7 days
        days = int(total_seconds // 86400)
        return f"in {days} {'day' if days == 1 else 'days'}"
    
    else:  # More than a week
        weeks = int(total_seconds // 604800)
        return f"in {weeks} {'week' if weeks == 1 else 'weeks'}"


def format_timestamp_with_relative(timestamp: datetime, reference_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Format timestamp with both ISO format and relative time
    
    Args:
        timestamp: The datetime to format
        reference_time: Reference time (defaults to now)
    
    Returns:
        Dict with 'iso', 'relative', and 'unix' fields
    """
    if not timestamp:
        return {
            "iso": None,
            "relative": "Unknown",
            "unix": None
        }
    
    # Ensure timezone-aware
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    return {
        "iso": timestamp.isoformat(),
        "relative": get_relative_time(timestamp, reference_time),
        "unix": int(timestamp.timestamp())
    }


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        String like "1h 22m", "45 minutes", "2 days"
    """
    if seconds < 60:
        return f"{int(seconds)} second{'s' if int(seconds) != 1 else ''}"
    
    elif seconds < 3600:  # Less than 1 hour
        minutes = int(seconds // 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    
    elif seconds < 86400:  # Less than 24 hours
        hours = int(seconds // 3600)
        remaining_minutes = int((seconds % 3600) // 60)
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        else:
            return f"{hours} hour{'s' if hours != 1 else ''}"
    
    else:  # 1+ days
        days = int(seconds // 86400)
        remaining_hours = int((seconds % 86400) // 3600)
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        else:
            return f"{days} day{'s' if days != 1 else ''}"


def localize_timestamp(timestamp: datetime, user_timezone: str = "UTC") -> datetime:
    """
    Localize UTC timestamp to user's timezone
    
    Args:
        timestamp: UTC datetime
        user_timezone: User's timezone string (e.g., "America/New_York")
    
    Returns:
        Localized datetime
    """
    if not timestamp:
        return timestamp
    
    # Ensure UTC timezone
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    try:
        user_tz = pytz.timezone(user_timezone)
        return timestamp.astimezone(user_tz)
    except Exception:
        # Fallback to UTC if timezone is invalid
        return timestamp


def get_time_parts(timestamp: datetime) -> Dict[str, Any]:
    """
    Get detailed time parts for advanced formatting
    
    Args:
        timestamp: The datetime to analyze
    
    Returns:
        Dict with detailed time information
    """
    if not timestamp:
        return {}
    
    now = datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    delta = now - timestamp
    total_seconds = delta.total_seconds()
    
    return {
        "seconds": int(total_seconds),
        "minutes": int(total_seconds // 60),
        "hours": int(total_seconds // 3600),
        "days": int(total_seconds // 86400),
        "weeks": int(total_seconds // 604800),
        "is_future": total_seconds < 0,
        "is_today": delta.days == 0 and total_seconds >= 0,
        "is_yesterday": delta.days == 1,
        "is_this_week": total_seconds < 604800,
        "is_this_month": total_seconds < 2592000,
        "formatted_date": timestamp.strftime("%Y-%m-%d"),
        "formatted_time": timestamp.strftime("%H:%M:%S"),
        "formatted_datetime": timestamp.strftime("%Y-%m-%d %H:%M:%S")
    }
