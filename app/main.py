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

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
from .api.v1 import auth, emails, tracking, analytics, webhooks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    
    yield
    
    # Shutdown
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
            "description": "Production server"
        },
        {
            "url": "http://localhost:8001",
            "description": "Development server"
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

# Custom middleware for request logging and timing
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing information"""
    start_time = time.time()
    
    # Log request
    logger.info(f"🔄 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log response
    status_emoji = "✅" if response.status_code < 400 else "❌"
    logger.info(f"{status_emoji} {request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
    
    # Add timing header
    response.headers["X-Process-Time"] = str(duration)
    
    return response

# Include API routers
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(emails.router, prefix=settings.api_v1_prefix)
app.include_router(tracking.router, prefix=settings.api_v1_prefix)
app.include_router(analytics.router, prefix=settings.api_v1_prefix)
app.include_router(webhooks.router, prefix=settings.api_v1_prefix)

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
