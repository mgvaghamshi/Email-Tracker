# 🔐 Refactored Authentication System

This document describes the new separated authentication system that cleanly divides dashboard JWT authentication from external API key access.

## 🎯 Overview

The authentication system now supports two distinct access methods:

1. **JWT Authentication** - For frontend dashboard users
2. **API Key Authentication** - For external programmatic access

Each method has its own security model, validation process, and use cases.

## 📁 File Structure

```
app/auth/
├── __init__.py                 # Authentication module
├── jwt_auth.py                 # JWT authentication for dashboard
└── api_key_auth.py            # API key authentication for external APIs

app/api/v1/
└── auth_examples.py           # Example usage of both auth methods

app/dependencies.py            # Legacy dependencies (kept for compatibility)
```

## 🔑 Authentication Methods

### 1. JWT Authentication (Dashboard)

**Purpose**: Frontend dashboard authentication for logged-in users

**Usage**:
```python
from app.auth.jwt_auth import get_current_user_from_jwt

@router.get("/dashboard/profile")
async def get_profile(
    current_user: User = Depends(get_current_user_from_jwt),
    db: Session = Depends(get_db)
):
    return {"user_id": current_user.id}
```

**Request Format**:
```http
GET /api/v1/dashboard/profile
Authorization: Bearer <JWT_TOKEN>
```

**Features**:
- ✅ Session-based authentication
- ✅ Token expiration handling
- ✅ User activity tracking
- ✅ Automatic token refresh (if implemented)

### 2. API Key Authentication (External APIs)

**Purpose**: Programmatic access for external applications and integrations

**Usage**:
```python
from app.auth.api_key_auth import get_user_from_api_key, require_api_key_scope

# Basic API key authentication
@router.get("/api/status")
async def get_status(
    current_user: User = Depends(get_user_from_api_key),
    db: Session = Depends(get_db)
):
    return {"status": "active"}

# API key with specific scope requirement
@router.post("/api/send-email")
async def send_email(
    current_user: User = Depends(lambda: require_api_key_scope("emails:send")),
    db: Session = Depends(get_db)
):
    return {"status": "sent"}
```

**Request Format**:
```http
POST /api/v1/api/send-email
x-api-key: et_abc123def456...
Content-Type: application/json
```

**Features**:
- ✅ Scope-based permissions
- ✅ Usage tracking and analytics
- ✅ Rate limiting per key
- ✅ Key expiration and deactivation
- ✅ Detailed audit logging

## 🛡️ Security Features

### JWT Security
- **Token Expiration**: Automatic expiration handling
- **Session Management**: Secure session tracking
- **User Verification**: Email verification requirements
- **Active User Check**: Ensures user account is active

### API Key Security
- **Scope-Based Access**: Fine-grained permissions
- **Usage Monitoring**: Track all API key usage
- **Expiration Control**: Set expiration dates for keys
- **Deactivation**: Instant key revocation
- **IP Tracking**: Monitor request origins
- **Rate Limiting**: Per-key rate limits

## 📊 Available Scopes

API keys can be assigned specific scopes to control access:

| Scope | Description |
|-------|-------------|
| `*` | Full access (admin) |
| `emails:send` | Send individual emails |
| `emails:bulk` | Send bulk emails |
| `emails:read` | Read email status and history |
| `campaigns:create` | Create new campaigns |
| `campaigns:read` | List and view campaigns |
| `campaigns:update` | Modify existing campaigns |
| `campaigns:delete` | Delete campaigns |
| `contacts:create` | Add new contacts |
| `contacts:read` | View contact lists |
| `contacts:update` | Modify contact information |
| `contacts:delete` | Remove contacts |
| `analytics:read` | Access analytics and reports |
| `templates:create` | Create email templates |
| `templates:read` | View templates |
| `templates:update` | Modify templates |
| `templates:delete` | Delete templates |

## 🔧 Migration Guide

### For Dashboard Routes

**Before**:
```python
from app.dependencies import get_authenticated_user

@router.get("/dashboard/data")
async def get_data(
    current_user: User = Depends(get_authenticated_user)
):
    pass
```

**After**:
```python
from app.auth.jwt_auth import get_current_user_from_jwt

@router.get("/dashboard/data")
async def get_data(
    current_user: User = Depends(get_current_user_from_jwt)
):
    pass
```

### For External API Routes

**Before**:
```python
from app.dependencies import get_authenticated_user

@router.post("/api/send")
async def send_email(
    current_user: User = Depends(get_authenticated_user)
):
    pass
```

**After**:
```python
from app.auth.api_key_auth import require_api_key_scope

@router.post("/api/send")
async def send_email(
    current_user: User = Depends(lambda: require_api_key_scope("emails:send"))
):
    pass
```

## 🧪 Testing the Authentication

### Test JWT Authentication

```bash
# 1. Login to get JWT token
curl -X POST "http://localhost:8001/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# 2. Use JWT token for dashboard routes
curl -X GET "http://localhost:8001/api/v1/examples/dashboard/profile" \
  -H "Authorization: Bearer <JWT_TOKEN>"
```

### Test API Key Authentication

```bash
# 1. Create API key via dashboard (JWT required)
curl -X POST "http://localhost:8001/api/v1/auth/api-keys" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test API Key", "scopes": ["emails:send", "campaigns:read"]}'

# 2. Use API key for external routes
curl -X GET "http://localhost:8001/api/v1/examples/api/status" \
  -H "x-api-key: <API_KEY>"

# 3. Test scoped access
curl -X POST "http://localhost:8001/api/v1/examples/api/send-email" \
  -H "x-api-key: <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"to": "test@example.com", "subject": "Test", "body": "Hello"}'
```

## 📈 Usage Analytics

The new system provides detailed analytics:

### JWT Analytics
- User login patterns
- Session durations
- Device/browser tracking
- Geographic access patterns

### API Key Analytics
- Request volume per key
- Endpoint usage patterns
- Error rates and types
- Rate limit violations
- Geographic API usage

## ⚙️ Configuration

### JWT Configuration
```python
# In app/core/user_security.py
JWT_EXPIRATION = 30 * 60  # 30 minutes
REFRESH_TOKEN_EXPIRATION = 7 * 24 * 60 * 60  # 7 days
```

### API Key Configuration
```python
# In app/auth/api_key_auth.py
DEFAULT_RATE_LIMIT = 100  # requests per minute
DEFAULT_DAILY_LIMIT = 10000  # requests per day
MAX_API_KEYS_PER_USER = 10
```

## 🚀 Examples in Action

See `app/api/v1/auth_examples.py` for complete working examples of:

- ✅ Dashboard profile access (JWT)
- ✅ External email sending (API Key + Scope)
- ✅ Campaign management (API Key + Scope)
- ✅ Analytics access (API Key + Scope)
- ✅ Public status endpoints (API Key - Basic)
- ✅ Advanced multi-scope operations

## 🔄 Backward Compatibility

The old `get_authenticated_user` dependency is still available in `app/dependencies.py` for backward compatibility, but new code should use the specific authentication methods:

- Use `get_current_user_from_jwt` for dashboard routes
- Use `get_user_from_api_key` or `require_api_key_scope` for external APIs

## 🎯 Benefits

✅ **Clear Separation**: Dashboard and API access are clearly separated
✅ **Enhanced Security**: Scope-based permissions for API keys
✅ **Better Monitoring**: Detailed usage tracking and analytics
✅ **Flexible Permissions**: Fine-grained access control
✅ **Rate Limiting**: Per-key rate limiting and usage controls
✅ **Easy Testing**: Clear testing patterns for both auth methods
✅ **Production Ready**: Built for scale with proper logging and monitoring
