"""
EmailTracker API - Professional email sending and tracking service

A comprehensive email infrastructure service similar to Mailgun, providing:
- Email sending with tracking
- Open and click tracking
- Bounce handling
- Analytics and reporting
- API key management
- Webhook notifications
"""

from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
import logging
import time
from typing import Dict, Any

from .config import settings
from .database.connection import init_db
from .dependencies import get_db
from .core.usage_middleware import track_api_usage_middleware, track_api_response
from .core.logging_config import setup_logging, get_logger
from .api.v1 import auth, emails, tracking, webhooks, campaigns, contacts, templates, users, admin, premium_features, analytics_dashboard
from .api.v1 import settings as settings_router

# Configure logging
setup_logging()
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("🚀 Starting EmailTracker API...")
    logger.info(f"📊 Environment: {'Development' if settings.debug else 'Production'}")
    logger.info(f"🔗 Base URL: {settings.base_url}")
    
    # Initialize database
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Start campaign scheduler
    try:
        from .services.scheduler import start_scheduler
        await start_scheduler()
        logger.info("✅ Campaign scheduler started successfully")
    except Exception as e:
        logger.error(f"❌ Campaign scheduler failed to start: {e}")
    
    yield
    
    # Shutdown
    try:
        from .services.scheduler import stop_scheduler
        await stop_scheduler()
        logger.info("✅ Campaign scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping campaign scheduler: {e}")
    
    logger.info("📴 EmailTracker API shutdown complete")


# Create FastAPI app with custom OpenAPI
app = FastAPI(
    title=settings.app_name,
    description="""
## EmailTracker API - Professional Email Infrastructure

A comprehensive email sending and tracking service designed for developers and businesses.
Similar to Mailgun, this API provides enterprise-grade email delivery with detailed analytics.

### 🚀 Key Features

- **Email Sending**: Send single emails or bulk campaigns
- **Real-time Tracking**: Track opens, clicks, bounces, and complaints
- **Analytics**: Comprehensive engagement analytics and reporting
- **API Keys**: Secure authentication with rate limiting
- **Webhooks**: Real-time event notifications
- **Bot Detection**: Intelligent filtering of bot traffic
- **High Deliverability**: Optimized for inbox delivery

### 🔐 Authentication

All API endpoints require authentication using API keys. Include your API key in the Authorization header:

```
Authorization: Bearer your_api_key_here
```

Create your first API key using the `/api/v1/auth/api-keys` endpoint.

### 📊 Rate Limits

Rate limits are enforced per API key:
- Default: 100 requests per minute, 10,000 per day
- Configurable per API key
- HTTP 429 response when exceeded

### 🔗 Useful Links

- [Documentation](https://docs.emailtracker.com)
- [SDKs and Libraries](https://github.com/emailtracker)
- [Status Page](https://status.emailtracker.com)
- [Support](mailto:support@emailtracker.com)

### 📝 Examples

#### Send a Single Email
```bash
curl -X POST "https://api.emailtracker.com/api/v1/emails/send" \\
     -H "Authorization: Bearer your_api_key" \\
     -H "Content-Type: application/json" \\
     -d '{
       "to_email": "user@example.com",
       "from_email": "sender@yourcompany.com",
       "from_name": "Your Company",
       "subject": "Welcome!",
       "html_content": "<h1>Welcome to our service!</h1>"
     }'
```

#### Get Campaign Analytics
```bash
curl -H "Authorization: Bearer your_api_key" \\
     "https://api.emailtracker.com/api/v1/analytics/campaigns/your_campaign_id"
```

### 📞 Support

Need help? Contact our support team:
- Email: support@emailtracker.com
- Documentation: https://docs.emailtracker.com
- Status: https://status.emailtracker.com
    """,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url=None,  # We'll create custom docs
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
    contact={
        "name": "EmailTracker Support",
        "email": "support@emailtracker.com",
        "url": "https://docs.emailtracker.com"
    },
    license_info={
        "name": "Commercial License",
        "url": "https://emailtracker.com/license"
    },
    servers=[
        {
            "url": settings.base_url,
            "description": "ColdEdge Email Service API"
        }
    ]
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Custom middleware for request logging, timing, and API usage tracking
@app.middleware("http")
async def log_requests_and_track_usage(request: Request, call_next):
    """Log all requests with timing information and track API usage"""
    start_time = time.time()
    
    # Get database session for usage tracking
    db_generator = get_db()
    db = next(db_generator)
    
    try:
        # Log request
        logger.info(f"🔄 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
        
        # Skip API usage tracking for frontend, auth, and public routes
        skip_tracking_paths = [
            "/api/v1/auth/",
            "/api/v1/users/",
            "/api/v1/templates/system",  # Public system templates
            "/api/usage",  # Frontend rate limit check endpoint
            "/auth/",
            "/login", 
            "/register",
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/favicon.ico",
            "/static/",
            "/",  # Root endpoint
        ]
        
        # Only track API usage for actual API endpoints with potential API keys
        should_track = not any(request.url.path.startswith(path) for path in skip_tracking_paths)
        
        if should_track:
            # Track API usage (rate limiting and validation) only for API endpoints
            await track_api_usage_middleware(request, db)
        
        # Process request
        response = await call_next(request)
        
        # Track the response only if we tracked the request
        if should_track:
            track_api_response(request, response.status_code, response, db)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        status_emoji = "✅" if response.status_code < 400 else "❌"
        logger.info(f"{status_emoji} {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response
        
    except HTTPException as e:
        # Handle rate limiting and other HTTP exceptions
        duration = time.time() - start_time
        logger.warning(f"⚠️ {request.method} {request.url.path} - {e.status_code} - {duration:.3f}s - {e.detail}")
        
        # For rate limit responses, create a proper response with headers
        if e.status_code == 429:
            from fastapi.responses import JSONResponse
            
            # Start with exception headers if available
            headers = {}
            if hasattr(e, 'headers') and e.headers:
                headers.update(e.headers)
            
            # Add additional rate limit headers if available from request state
            if hasattr(request.state, 'rate_limit_headers'):
                headers.update(request.state.rate_limit_headers)
            
            # Add timing header
            headers["X-Process-Time"] = str(duration)
            
            return JSONResponse(
                status_code=429,
                content=e.detail,
                headers=headers
            )
        
        raise e
    finally:
        # Close database session
        try:
            next(db_generator)
        except StopIteration:
            pass

# Include API routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)

# Core API endpoints
app.include_router(emails.router, prefix=settings.api_v1_prefix)
app.include_router(campaigns.router, prefix=settings.api_v1_prefix)

# Premium features for SaaS dashboard
try:
    app.include_router(premium_features.router, prefix=settings.api_v1_prefix, tags=["Premium Features"])
    logger.info("✅ Premium features endpoints loaded successfully")
except ImportError as e:
    logger.warning(f"⚠️ Premium features not available: {e}")

# Load standard endpoints
app.include_router(tracking.router, prefix=settings.api_v1_prefix)
app.include_router(analytics_dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(webhooks.router, prefix=settings.api_v1_prefix)
app.include_router(contacts.router, prefix=settings.api_v1_prefix)
app.include_router(templates.router, prefix=settings.api_v1_prefix)
app.include_router(settings_router.router, prefix=settings.api_v1_prefix)

# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns the current status of the EmailTracker API service.
    Use this endpoint to monitor service availability.
    """
    return {
        "status": "healthy",
        "service": "EmailTracker API",
        "version": settings.app_version,
        "environment": "development" if settings.debug else "production",
        "timestamp": time.time()
    }

@app.get("/api/usage", tags=["Usage"], include_in_schema=False)
async def get_usage_status():
    """
    Frontend usage status endpoint
    
    Returns rate limit usage information for the frontend.
    This endpoint is used by the frontend to check rate limit status.
    """
    # Return mock data for now - in production this would check user's actual usage
    return {
        "limit": 1000,
        "remaining": 950,
        "resetTime": int(time.time() + 3600),  # Reset in 1 hour
        "used": 50,
        "percentage": 5.0
    }

@app.get("/api/test/templates", tags=["Test"], include_in_schema=False)
async def test_templates(db: Session = Depends(get_db)):
    """
    Test endpoint to check templates without authentication
    """
    from .database.models import Template
    templates = db.query(Template).all()
    return {
        "total": len(templates),
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "user_id": t.user_id
            } for t in templates
        ]
    }

@app.get("/api/test/contacts", tags=["Test"], include_in_schema=False)
async def test_contacts(db: Session = Depends(get_db)):
    """
    Test endpoint to check contacts without authentication
    """
    from .database.models import Contact
    contacts = db.query(Contact).all()
    return {
        "total": len(contacts),
        "contacts": [
            {
                "id": c.id,
                "email": c.email,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "status": c.status,
                "user_id": c.user_id
            } for c in contacts
        ]
    }

@app.get("/api/test/campaigns", tags=["Test"], include_in_schema=False)
async def test_campaigns(db: Session = Depends(get_db)):
    """
    Test endpoint to check campaigns without authentication
    """
    from .database.models import Campaign
    campaigns = db.query(Campaign).all()
    return {
        "total": len(campaigns),
        "campaigns": [
            {
                "id": c.id,
                "name": c.name,
                "status": c.status,
                "user_id": c.user_id,
                "subject": c.subject,
                "description": c.description,
                "recipients_count": 0,
                "sent_count": 0,
                "open_rate": 0.0,
                "click_rate": 0.0,
                "created_at": c.created_at.isoformat() if c.created_at else None
            } for c in campaigns
        ]
    }

@app.get("/", tags=["Health"])
async def root():
    """
    API root endpoint
    
    Welcome message and basic API information.
    """
    return {
        "message": "Welcome to EmailTracker API",
        "version": settings.app_version,
        "documentation": f"{settings.base_url}/docs",
        "health": f"{settings.base_url}/health",
        "openapi": f"{settings.base_url}/api/v1/openapi.json"
    }

# Root-level unsubscribe endpoint for backward compatibility
@app.get("/unsubscribe/{tracker_id}", include_in_schema=False)
async def root_unsubscribe(tracker_id: str, db: Session = Depends(get_db)):
    """
    Root-level unsubscribe endpoint for backward compatibility
    
    This handles unsubscribe requests that come directly to /unsubscribe/{tracker_id}
    instead of the full API path /api/v1/track/unsubscribe/{tracker_id}
    """
    from .api.v1.tracking import unsubscribe
    return await unsubscribe(tracker_id, db)

# Custom documentation endpoints
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with branding"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Interactive API Documentation",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png"
    )

@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Custom ReDoc documentation"""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - API Documentation",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
    )

# Custom OpenAPI schema
def custom_openapi():
    """Generate custom OpenAPI schema with additional metadata"""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # Add custom security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "API Key",
            "description": "Enter your API key in the format: your_api_key_here"
        }
    }
    
    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]
    
    # Add tags metadata
    openapi_schema["tags"] = [
        {
            "name": "Health",
            "description": "Service health and status endpoints"
        },
        {
            "name": "Authentication",
            "description": "API key management and authentication"
        },
        {
            "name": "Email Sending",
            "description": "Send single emails and bulk campaigns with tracking"
        },
        {
            "name": "Tracking",
            "description": "Email open and click tracking endpoints"
        },
        {
            "name": "Analytics",
            "description": "Email analytics, engagement metrics, and reporting"
        },
        {
            "name": "Webhooks",
            "description": "Real-time event notifications via webhooks"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler with detailed error responses"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
                "type": "http_exception",
                "timestamp": time.time(),
                "path": str(request.url.path)
            }
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unexpected errors"""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
                "type": "internal_error",
                "timestamp": time.time(),
                "path": str(request.url.path)
            }
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
        log_level="info" if not settings.debug else "debug"
    )
