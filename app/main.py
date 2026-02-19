from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from contextlib import asynccontextmanager

import logging
logger = logging.getLogger(__name__)

from .db import SessionLocal, init_db

# Import all API routers
from .api.v1.users import router as users_router
from .api.v1.admin import router as admin_router
from .api.v1.auth_keys import router as auth_keys_router
from .api.v1.emails import router as emails_router
from .api.v1.campaigns import router as campaigns_router
from .api.v1.templates import router as templates_router
from .api.v1.contacts import router as contacts_router
from .api.v1.analytics import router as analytics_router
from .api.v1.webhooks import router as webhooks_router
from .api.v1.tracking import router as tracking_router
from .api.v1.settings import router as settings_router
from .api.v1.premium import router as premium_router

# Initialize database tables
init_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown
    pass

app = FastAPI(
    title="EmailTracker API",
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

### 🔑 Authentication

All API endpoints require authentication using API keys or JWT tokens. Include your key in the Authorization header:

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
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://mail-tantra.marvonix.com",
        "http://localhost:3000",
        "https://emailtrackerapi.marvonix.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(auth_keys_router)
app.include_router(emails_router)
app.include_router(campaigns_router)
app.include_router(templates_router)
app.include_router(contacts_router)
app.include_router(analytics_router)
app.include_router(webhooks_router)
app.include_router(tracking_router)
app.include_router(settings_router)
app.include_router(premium_router)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - API welcome message"""
    return {
        "message": "EmailTracker API is running",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json"
    }


@app.get("/health", tags=["Health"])
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    
    Service health and status endpoints
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "database": "disconnected"
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
