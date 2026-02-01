"""
CORS utilities and helpers for managing cross-origin requests
"""
from fastapi import Request
from fastapi.responses import Response


def add_cors_headers(response: Response, request: Request) -> Response:
    """Add CORS headers to a response"""
    origin = request.headers.get("origin")
    
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Expose-Headers"] = (
            "Content-Type, X-Process-Time, X-RateLimit-Limit, "
            "X-RateLimit-Remaining, X-RateLimit-Reset"
        )
    else:
        # Default to allowing all origins if no origin header
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Expose-Headers"] = (
            "Content-Type, X-Process-Time, X-RateLimit-Limit, "
            "X-RateLimit-Remaining, X-RateLimit-Reset"
        )
    
    return response


def get_cors_headers(request: Request) -> dict:
    """Get CORS headers as a dictionary"""
    origin = request.headers.get("origin")
    
    headers = {
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS, HEAD",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Expose-Headers": (
            "Content-Type, X-Process-Time, X-RateLimit-Limit, "
            "X-RateLimit-Remaining, X-RateLimit-Reset"
        ),
    }
    
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    else:
        headers["Access-Control-Allow-Origin"] = "*"
    
    return headers
