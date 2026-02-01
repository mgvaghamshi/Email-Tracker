"""
Device detection and IP geolocation utilities
"""
import re
import requests
from typing import Dict, Any, Optional, Tuple
from user_agents import parse as parse_user_agent
import json


def parse_device_info(user_agent: str) -> Dict[str, Any]:
    """Parse user agent string to extract device information"""
    if not user_agent:
        return {
            "device_type": "Unknown",
            "device_brand": "Unknown",
            "device_model": "Unknown",
            "browser_name": "Unknown Browser",
            "browser_version": "Unknown",
            "os_name": "Unknown OS",
            "os_version": "Unknown",
            "is_mobile": False,
            "is_tablet": False,
            "is_desktop": False,
            "is_bot": False
        }
    
    try:
        ua = parse_user_agent(user_agent)
        
        # Determine device type
        device_type = "Desktop"
        if ua.is_mobile:
            device_type = "Mobile"
        elif ua.is_tablet:
            device_type = "Tablet"
        elif ua.is_bot:
            device_type = "Bot"
        
        return {
            "device_type": device_type,
            "device_brand": ua.device.brand or "Unknown",
            "device_model": ua.device.model or "Unknown",
            "browser_name": ua.browser.family or "Unknown Browser",
            "browser_version": ua.browser.version_string or "Unknown",
            "os_name": ua.os.family or "Unknown OS",
            "os_version": ua.os.version_string or "Unknown",
            "is_mobile": ua.is_mobile,
            "is_tablet": ua.is_tablet,
            "is_desktop": not (ua.is_mobile or ua.is_tablet or ua.is_bot),
            "is_bot": ua.is_bot
        }
    except Exception:
        return {
            "device_type": "Unknown",
            "device_brand": "Unknown",
            "device_model": "Unknown",
            "browser_name": "Unknown Browser",
            "browser_version": "Unknown",
            "os_name": "Unknown OS",
            "os_version": "Unknown",
            "is_mobile": False,
            "is_tablet": False,
            "is_desktop": False,
            "is_bot": False
        }


def get_device_display_name(device_info: Dict[str, Any]) -> str:
    """Generate a human-readable device name"""
    try:
        if device_info.get("is_bot"):
            return f"Bot: {device_info.get('browser_name', 'Unknown')}"
        
        device_type = device_info.get("device_type", "Unknown")
        browser = device_info.get("browser_name", "Unknown Browser")
        os_name = device_info.get("os_name", "Unknown OS")
        
        if device_type == "Mobile":
            brand = device_info.get("device_brand", "")
            model = device_info.get("device_model", "")
            if brand and model and brand != "Unknown" and model != "Unknown":
                return f"{brand} {model}"
            elif brand and brand != "Unknown":
                return f"{brand} Mobile"
            else:
                return f"Mobile ({browser})"
        
        elif device_type == "Tablet":
            brand = device_info.get("device_brand", "")
            model = device_info.get("device_model", "")
            if brand and model and brand != "Unknown" and model != "Unknown":
                return f"{brand} {model} Tablet"
            else:
                return f"Tablet ({browser})"
        
        else:  # Desktop
            if os_name and os_name != "Unknown OS":
                return f"{os_name} ({browser})"
            else:
                return f"Desktop ({browser})"
                
    except Exception:
        return "Unknown Device"


def get_location_from_ip(ip_address: str) -> Optional[str]:
    """Get approximate location from IP address using ipapi.co (free tier)"""
    if not ip_address or ip_address in ["127.0.0.1", "localhost", "::1"]:
        return "Local"
    
    try:
        # Use ipapi.co free service (1000 requests/month)
        response = requests.get(
            f"https://ipapi.co/{ip_address}/json/",
            timeout=3,
            headers={"User-Agent": "EmailTracker/1.0"}
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check for errors
            if data.get("error"):
                return None
            
            city = data.get("city")
            region = data.get("region")
            country = data.get("country_name")
            
            if city and country:
                if region and region != city:
                    return f"{city}, {region}, {country}"
                else:
                    return f"{city}, {country}"
            elif country:
                return country
            else:
                return None
        
    except Exception:
        pass
    
    return None


def is_same_device(device_info1: Dict[str, Any], device_info2: Dict[str, Any]) -> bool:
    """Check if two device info objects represent the same device"""
    if not device_info1 or not device_info2:
        return False
    
    # Compare key device characteristics
    same_browser = (
        device_info1.get("browser_name") == device_info2.get("browser_name") and
        device_info1.get("browser_version") == device_info2.get("browser_version")
    )
    
    same_os = (
        device_info1.get("os_name") == device_info2.get("os_name") and
        device_info1.get("os_version") == device_info2.get("os_version")
    )
    
    same_device_type = device_info1.get("device_type") == device_info2.get("device_type")
    
    return same_browser and same_os and same_device_type


def is_known_location(ip_address: str, user_previous_ips: list) -> bool:
    """Check if an IP address is from a known location"""
    if not ip_address or not user_previous_ips:
        return False
    
    # Simple check - if exact IP was used before
    if ip_address in user_previous_ips:
        return True
    
    # Could add more sophisticated location-based checking here
    # For now, just exact IP match
    return False
