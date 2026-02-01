# ColdEdge Email Service - Complete Project Documentation

**Version:** 1.0.0  
**Last Updated:** January 29, 2026  
**Status:** Production Ready

---

## 📋 Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Technology Stack](#technology-stack)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)
7. [Security Implementation](#security-implementation)
8. [SaaS Features](#saas-features)
9. [Deployment](#deployment)
10. [Future Roadmap](#future-roadmap)

---

## 🎯 Project Overview

ColdEdge Email Service is a professional email infrastructure API service designed for businesses and developers. Similar to Mailgun or SendGrid, it provides enterprise-grade email delivery, tracking, and analytics capabilities.

### Key Objectives

- **Email Infrastructure as a Service**: Provide reliable email sending and tracking API
- **SaaS Dashboard**: Complete web-based management interface for users
- **Multi-tier Subscription**: Free, Pro, and Enterprise plans with feature gating
- **Enterprise Security**: 2FA, API keys, rate limiting, audit logs
- **Campaign Management**: Create, schedule, and track email campaigns
- **Analytics**: Comprehensive tracking and reporting

---

## 🏗️ Architecture

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                 Frontend Dashboard                       │
│              (Next.js 15 + React 18)                    │
│              Port: 3000                                 │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ REST API (JWT Auth)
                  │
┌─────────────────▼───────────────────────────────────────┐
│              Backend API Service                         │
│              (FastAPI + Python 3.11)                    │
│              Port: 8001                                 │
├──────────────────────────────────────────────────────────┤
│  ├─ Authentication (JWT + Session Management)           │
│  ├─ Authorization (Role-Based Access Control)           │
│  ├─ API Key Management                                  │
│  ├─ Rate Limiting & Usage Tracking                      │
│  ├─ Campaign Scheduler (Background Tasks)               │
│  └─ Email Service (SMTP Integration)                    │
└─────────────────┬───────────────────────────────────────┘
                  │
                  │ SQLAlchemy ORM
                  │
┌─────────────────▼───────────────────────────────────────┐
│              Database Layer                              │
│              (SQLite Dev / PostgreSQL Prod)             │
│                                                          │
│  ├─ Users & Authentication                              │
│  ├─ Campaigns & Templates                               │
│  ├─ Contacts & Recipients                               │
│  ├─ Email Tracking & Analytics                          │
│  ├─ Subscriptions & Billing                             │
│  └─ API Keys & Security Audit                           │
└──────────────────────────────────────────────────────────┘
```

### Directory Structure

```
emailtracker/
├── app/
│   ├── api/v1/          # API endpoints
│   │   ├── auth.py      # Authentication endpoints
│   │   ├── campaigns.py # Campaign management
│   │   ├── contacts.py  # Contact management
│   │   ├── templates.py # Email templates
│   │   ├── analytics_dashboard.py
│   │   ├── api_keys.py  # API key management
│   │   ├── two_factor.py # 2FA
│   │   ├── subscription.py # Plans & billing
│   │   ├── recurring_campaigns.py # Pro+ feature
│   │   └── premium_features.py
│   ├── auth/            # Authentication logic
│   │   └── jwt_auth.py  # JWT token handling
│   ├── core/            # Core utilities
│   │   ├── security.py  # Password hashing, API keys
│   │   ├── user_security.py # User auth logic
│   │   ├── cors_utils.py # CORS handling
│   │   └── logging_config.py
│   ├── database/        # Database models
│   │   ├── models.py    # Email & campaign models
│   │   ├── user_models.py # User & auth models
│   │   ├── subscription_models.py
│   │   └── connection.py
│   ├── services/        # Business logic
│   │   ├── scheduler.py # Campaign scheduling
│   │   ├── email_service.py # Email sending
│   │   ├── subscription_service.py
│   │   └── user_onboarding.py
│   ├── schemas/         # Pydantic schemas
│   │   ├── campaign.py
│   │   ├── user.py
│   │   ├── auth.py
│   │   └── subscription.py
│   ├── config.py        # Configuration management
│   └── main.py          # FastAPI application entry
├── alembic/             # Database migrations
├── docs/                # Documentation
├── exports/             # Data export files
├── logs/                # Application logs
├── requirements.txt     # Python dependencies
├── run.py              # Application runner
└── Dockerfile          # Container configuration
```

---

## ✨ Features

### 1. Core Email Features

#### Email Sending
- ✅ Single email sending with tracking pixels
- ✅ Bulk email campaigns (up to 50,000 recipients per campaign)
- ✅ HTML and plain text email support
- ✅ Email personalization with merge tags
- ✅ Attachment support
- ✅ SMTP integration with fallback providers
- ✅ Bounce handling and suppression lists
- ✅ Unsubscribe link management

#### Campaign Management
- ✅ Create, edit, delete campaigns
- ✅ Campaign status management (draft, scheduled, sending, completed)
- ✅ Schedule campaigns for future sending
- ✅ Timezone-aware scheduling (user's local timezone)
- ✅ Campaign cloning and templates
- ✅ A/B testing support (template variants)
- ✅ Pause/resume active campaigns
- ✅ Campaign version history

#### Recurring Campaigns (Pro+ Feature)
- ✅ Daily, weekly, monthly, yearly schedules
- ✅ Custom frequency configuration
- ✅ Start and end date management
- ✅ Maximum occurrence limits
- ✅ Automatic recipient list updates
- ✅ Performance tracking across occurrences

### 2. Contact Management

- ✅ Contact CRUD operations
- ✅ Bulk contact import (CSV)
- ✅ Contact tagging and segmentation
- ✅ Custom field support (JSON)
- ✅ Contact status management (active, unsubscribed, bounced)
- ✅ Duplicate detection and merging
- ✅ Contact engagement history
- ✅ Export contacts to CSV

### 3. Template System

- ✅ Template CRUD operations
- ✅ Rich text editor support
- ✅ Template version control
- ✅ Template folders/organization
- ✅ System templates (provided by platform)
- ✅ User custom templates
- ✅ Template preview
- ✅ Variable/merge tag support

### 4. Analytics & Tracking

#### Email Tracking
- ✅ Open tracking (pixel-based)
- ✅ Click tracking (link proxying)
- ✅ Delivery tracking
- ✅ Bounce tracking (hard/soft bounces)
- ✅ Spam complaint tracking
- ✅ Unsubscribe tracking
- ✅ Bot detection and filtering
- ✅ Geographic tracking (IP-based)
- ✅ Device and browser detection

#### Campaign Analytics
- ✅ Real-time campaign metrics
- ✅ Open rate, click rate, bounce rate
- ✅ Engagement timeline
- ✅ Top clicked links
- ✅ Geographic distribution
- ✅ Device breakdown
- ✅ Export analytics to CSV
- ✅ Comparative analytics (A/B testing results)

#### Dashboard Analytics
- ✅ Overview statistics
- ✅ Campaign performance trends
- ✅ Email volume charts
- ✅ Engagement metrics
- ✅ Recent activity feed
- ✅ Usage statistics vs. plan limits

### 5. Authentication & Security

#### User Authentication
- ✅ Email/password registration and login
- ✅ JWT-based authentication
- ✅ Session management (multi-device support)
- ✅ Refresh token rotation
- ✅ "Remember me" functionality
- ✅ Session revocation (logout all devices)
- ✅ Email verification
- ✅ Password reset flow

#### Two-Factor Authentication (2FA)
- ✅ TOTP (Time-based One-Time Password)
- ✅ QR code generation for authenticator apps
- ✅ Backup codes (10 one-time use codes)
- ✅ 2FA enforcement for admin users
- ✅ Trusted device management
- ✅ Recovery options

#### API Key Management
- ✅ Create multiple API keys per user
- ✅ Key naming and organization
- ✅ Scope-based permissions (read, write, admin)
- ✅ Rate limiting per API key
- ✅ Key expiration dates
- ✅ Usage tracking and analytics
- ✅ Key revocation
- ✅ Last used tracking

#### Security Features
- ✅ Password strength requirements
- ✅ Account lockout after failed attempts (5 tries, 30-minute lockout)
- ✅ Brute force protection
- ✅ Rate limiting (per IP and per user)
- ✅ Security audit logs
- ✅ CORS protection
- ✅ SQL injection prevention (parameterized queries)
- ✅ XSS protection
- ✅ CSRF protection
- ✅ Secure password hashing (bcrypt)
- ✅ Secure token generation (cryptographically secure)

### 6. Subscription & Billing (SaaS)

#### Subscription Plans
- ✅ **Free Tier**
  - 100 emails/month
  - 100 contacts
  - 3 campaigns
  - Basic templates (5)
  - 7-day analytics retention
  - Community support

- ✅ **Pro Tier** ($29/month)
  - 10,000 emails/month
  - 5,000 contacts
  - Unlimited campaigns
  - All templates
  - Recurring campaigns
  - 90-day analytics retention
  - Priority email support
  - Custom domains (3)
  - API access (10 keys)
  - A/B testing

- ✅ **Enterprise Tier** ($99/month)
  - 50,000 emails/month
  - 25,000 contacts
  - Unlimited campaigns
  - All features
  - 365-day analytics retention
  - Dedicated support
  - Unlimited custom domains
  - Unlimited API keys
  - Advanced segmentation
  - Webhook integrations
  - White-label options

#### Plan Management
- ✅ Subscription status tracking (active, trial, expired, cancelled)
- ✅ Usage tracking against limits
- ✅ Soft and hard limit enforcement
- ✅ Plan upgrade/downgrade
- ✅ Trial period (7 days)
- ✅ Feature access control based on plan
- ✅ Usage overage warnings
- ✅ Billing cycle management
- ✅ Proration on plan changes

### 7. User Management

- ✅ User profile management
- ✅ Profile picture/avatar upload
- ✅ Timezone and locale preferences
- ✅ Email preferences
- ✅ Account settings
- ✅ Password change
- ✅ Account deletion
- ✅ Data export (GDPR compliance)
- ✅ Session management
- ✅ Activity history

### 8. Settings & Configuration

#### User Settings
- ✅ Timezone configuration
- ✅ Email notification preferences
- ✅ Default email settings (from name, reply-to)
- ✅ Signature management
- ✅ Language/locale preferences

#### System Settings
- ✅ SMTP server configuration
- ✅ Email sending limits
- ✅ Rate limiting configuration
- ✅ Feature flags
- ✅ Maintenance mode
- ✅ System templates management

---

## 🛠️ Technology Stack

### Backend
- **Framework**: FastAPI 0.104.1
- **Language**: Python 3.11
- **ORM**: SQLAlchemy 2.0.23
- **Database**: SQLite (dev), PostgreSQL (prod)
- **Authentication**: JWT (PyJWT 2.8.0)
- **Validation**: Pydantic 2.5.0
- **Password Hashing**: bcrypt 4.1.2
- **2FA**: pyotp 2.9.0
- **Migrations**: Alembic 1.13.0
- **ASGI Server**: Uvicorn 0.24.0

### Frontend
- **Framework**: Next.js 15.4.4
- **UI Library**: React 18
- **Styling**: Tailwind CSS
- **Component Library**: Radix UI
- **Forms**: React Hook Form
- **State Management**: React Context + Hooks
- **HTTP Client**: Fetch API
- **Icons**: Lucide React
- **Charts**: Recharts

### DevOps & Deployment
- **Containerization**: Docker
- **Orchestration**: Docker Compose
- **Web Server**: Nginx (reverse proxy)
- **Hosting**: Render.com (current), AWS/GCP (future)
- **CI/CD**: GitHub Actions (planned)
- **Monitoring**: Built-in logging + external APM (planned)

---

## 📊 Database Schema

### Core Tables

#### Users & Authentication
- `users` - User accounts
- `user_sessions` - Active user sessions
- `login_attempts` - Failed login tracking
- `password_resets` - Password reset tokens
- `email_verifications` - Email verification tokens
- `roles` - User roles (admin, user)
- `user_roles` - User-role associations
- `two_factor_auth` - 2FA settings
- `two_factor_attempts` - 2FA verification attempts
- `two_factor_sessions` - Trusted devices
- `security_audit_logs` - Security event logging
- `password_reset_tokens` - Secure reset tokens
- `security_settings` - Security configuration

#### Campaigns & Emails
- `campaigns` - Email campaigns
- `campaign_versions` - Campaign history
- `campaign_recipients` - Campaign-recipient mapping
- `email_trackers` - Email tracking data
- `email_events` - Email lifecycle events
- `email_clicks` - Click tracking
- `email_bounces` - Bounce handling
- `recurring_campaigns` - Recurring campaign config (Pro+)
- `recurring_campaign_occurrences` - Execution history

#### Contacts & Templates
- `contacts` - Contact database
- `templates` - Email templates
- `template_versions` - Template history
- `template_folders` - Template organization

#### Subscription & Billing
- `subscription_plans` - Available plans
- `user_subscriptions` - User subscriptions
- `feature_usage_logs` - Usage tracking
- `user_settings` - User preferences

#### API & Webhooks
- `api_keys` - API key management
- `api_key_usage` - API usage tracking
- `webhook_events` - Webhook delivery log

---

## 🔌 API Endpoints

### Authentication
- `POST /api/v1/users/register` - User registration
- `POST /api/v1/users/login` - User login
- `POST /api/v1/users/refresh` - Refresh access token
- `POST /api/v1/users/logout` - Logout current session
- `POST /api/v1/users/logout-all` - Logout all sessions
- `POST /api/v1/users/password-reset` - Request password reset
- `POST /api/v1/users/password-reset-confirm` - Confirm reset
- `POST /api/v1/users/verify-email` - Verify email address

### Two-Factor Authentication
- `POST /api/v1/two-factor/setup` - Enable 2FA
- `POST /api/v1/two-factor/verify-setup` - Confirm 2FA setup
- `POST /api/v1/two-factor/verify` - Verify 2FA code
- `DELETE /api/v1/two-factor/disable` - Disable 2FA
- `POST /api/v1/two-factor/backup-codes` - Generate backup codes

### API Keys
- `POST /api/v1/auth/api-keys` - Create API key
- `GET /api/v1/auth/api-keys` - List API keys
- `GET /api/v1/auth/api-keys/{id}` - Get API key details
- `PATCH /api/v1/auth/api-keys/{id}` - Update API key
- `DELETE /api/v1/auth/api-keys/{id}` - Revoke API key

### Campaigns
- `POST /api/v1/campaigns` - Create campaign
- `GET /api/v1/campaigns` - List campaigns
- `GET /api/v1/campaigns/{id}` - Get campaign details
- `PATCH /api/v1/campaigns/{id}` - Update campaign
- `DELETE /api/v1/campaigns/{id}` - Delete campaign
- `POST /api/v1/campaigns/{id}/send` - Send campaign
- `POST /api/v1/campaigns/{id}/schedule` - Schedule campaign
- `POST /api/v1/campaigns/{id}/pause` - Pause campaign
- `POST /api/v1/campaigns/{id}/resume` - Resume campaign
- `POST /api/v1/campaigns/{id}/clone` - Clone campaign

### Recurring Campaigns (Pro+)
- `POST /api/v1/recurring-campaigns` - Create recurring campaign
- `GET /api/v1/recurring-campaigns` - List recurring campaigns
- `GET /api/v1/recurring-campaigns/{id}` - Get details
- `PATCH /api/v1/recurring-campaigns/{id}` - Update
- `DELETE /api/v1/recurring-campaigns/{id}` - Delete
- `POST /api/v1/recurring-campaigns/{id}/pause` - Pause
- `POST /api/v1/recurring-campaigns/{id}/resume` - Resume

### Contacts
- `POST /api/v1/contacts` - Create contact
- `GET /api/v1/contacts` - List contacts
- `GET /api/v1/contacts/{id}` - Get contact details
- `PATCH /api/v1/contacts/{id}` - Update contact
- `DELETE /api/v1/contacts/{id}` - Delete contact
- `POST /api/v1/contacts/bulk` - Bulk create contacts
- `POST /api/v1/contacts/import` - Import from CSV
- `POST /api/v1/contacts/export` - Export to CSV

### Templates
- `POST /api/v1/templates` - Create template
- `GET /api/v1/templates` - List templates
- `GET /api/v1/templates/system` - List system templates
- `GET /api/v1/templates/{id}` - Get template details
- `PATCH /api/v1/templates/{id}` - Update template
- `DELETE /api/v1/templates/{id}` - Delete template
- `POST /api/v1/templates/{id}/clone` - Clone template

### Analytics
- `GET /api/v1/analytics/dashboard` - Dashboard overview
- `GET /api/v1/analytics/campaigns/{id}` - Campaign analytics
- `GET /api/v1/analytics/campaigns/{id}/export` - Export analytics
- `GET /api/v1/analytics/trends` - Analytics trends
- `GET /api/v1/analytics/engagement` - Engagement metrics

### Tracking
- `GET /api/v1/track/open/{tracker_id}` - Track email open
- `GET /api/v1/track/click/{tracker_id}` - Track link click
- `GET /api/v1/track/unsubscribe/{tracker_id}` - Unsubscribe

### Subscriptions
- `GET /api/v1/subscription/plans` - List available plans
- `GET /api/v1/subscription/current` - Get current subscription
- `POST /api/v1/subscription/upgrade` - Upgrade plan
- `POST /api/v1/subscription/downgrade` - Downgrade plan
- `POST /api/v1/subscription/cancel` - Cancel subscription
- `GET /api/v1/subscription/usage` - Get usage statistics

### User Management
- `GET /api/v1/users/me` - Get current user
- `PATCH /api/v1/users/me` - Update profile
- `POST /api/v1/users/password-change` - Change password
- `GET /api/v1/users/sessions` - List sessions
- `DELETE /api/v1/users/sessions/{id}` - Revoke session
- `POST /api/v1/users/export-data` - Export user data

### Settings
- `GET /api/v1/settings` - Get user settings
- `PATCH /api/v1/settings` - Update settings
- `POST /api/v1/settings/export-data` - Export all data

---

## 🔐 Security Implementation

### Password Security
- Bcrypt hashing with salt rounds: 12
- Minimum length: 8 characters
- Must contain: uppercase, lowercase, number, special character
- Password history: 5 previous passwords
- Password expiry: 90 days (optional)

### Session Management
- JWT access tokens: 30 minutes expiry
- JWT refresh tokens: 7 days expiry (30 days with "remember me")
- Token rotation on refresh
- Session tracking with device info
- Concurrent session limit: 5 devices

### Rate Limiting
- Login attempts: 5 per 15 minutes per email
- API requests: 100 per minute (default), configurable per key
- Registration: 3 per hour per IP
- Password reset: 3 per hour per email

### API Key Security
- Keys generated using cryptographically secure random
- Keys hashed before storage (SHA-256)
- Prefix stored for identification (first 8 characters)
- Automatic expiration support
- Last used timestamp tracking

### Audit Logging
- All security events logged
- Failed login attempts
- Password changes
- API key operations
- Session creation/revocation
- 2FA operations
- Data exports

---

## 💎 SaaS Features

### User Onboarding
1. Registration with email verification
2. Email verification required before access
3. Default free plan assignment
4. System template access
5. Welcome email (future)
6. Onboarding tutorial (future)

### Feature Gating
- Template-based access control
- Plan-based feature checks
- Usage limit enforcement
- Soft limits with warnings
- Hard limits with blocking
- Upgrade prompts when limits reached

### Usage Tracking
- Real-time usage monitoring
- Daily/monthly aggregation
- Per-feature tracking
- Historical data retention
- Usage alerts
- Overage detection

### Plan Management
- Self-service plan changes
- Immediate upgrade activation
- Proration handling
- Downgrade queuing (end of period)
- Trial-to-paid conversion
- Subscription renewal handling

---

## 🚀 Deployment

### Development Setup
```bash
# Backend
cd emailtracker
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py

# Frontend
cd dashboard-emailtracker
npm install
npm run dev
```

### Production Deployment

#### Docker Deployment
```bash
# Build and run with Docker Compose
docker-compose up -d

# Access:
# - Backend: http://localhost:8001
# - Frontend: http://localhost:3000
```

#### Render.com Deployment
- Backend: Web Service (Python)
- Frontend: Static Site (Next.js)
- Database: PostgreSQL
- See `DEPLOY_TO_RENDER.md` for details

### Environment Configuration

#### Backend `.env`
```ini
# Database
DATABASE_URL=sqlite:///./email_tracker.db
# or for PostgreSQL:
# DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=noreply@example.com
SMTP_FROM_NAME=ColdEdge

# CORS
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com

# Features
ENABLE_REGISTRATION=true
ENABLE_2FA=true
ENABLE_API_KEYS=true

# Limits
DEFAULT_RATE_LIMIT_PER_MINUTE=100
DEFAULT_RATE_LIMIT_PER_DAY=10000
```

#### Frontend `.env.local`
```ini
NEXT_PUBLIC_API_URL=http://localhost:8001
NEXT_PUBLIC_APP_NAME=ColdEdge Email Service
NEXT_PUBLIC_SUPPORT_EMAIL=support@example.com
```

---

## 🗺️ Future Roadmap

### Phase 1: Core Enhancements (Q1 2026)
- [ ] Email template builder (drag-and-drop)
- [ ] Advanced segmentation
- [ ] Custom fields for contacts
- [ ] Import/export improvements
- [ ] Mobile app (React Native)

### Phase 2: Integration & Automation (Q2 2026)
- [ ] Webhook integrations
- [ ] Zapier integration
- [ ] REST API webhooks for events
- [ ] Workflow automation
- [ ] Conditional sending logic
- [ ] Drip campaigns

### Phase 3: Advanced Features (Q3 2026)
- [ ] Machine learning for send time optimization
- [ ] Predictive analytics
- [ ] Advanced A/B testing (multivariate)
- [ ] Heat maps for email engagement
- [ ] Spam score checking
- [ ] Email preview across clients

### Phase 4: Enterprise Features (Q4 2026)
- [ ] Multi-user accounts (teams)
- [ ] Role-based permissions (granular)
- [ ] White-label platform
- [ ] Custom domain email sending
- [ ] Dedicated IP addresses
- [ ] DKIM, SPF, DMARC management
- [ ] Advanced reporting and exports

### Phase 5: Scale & Performance (2027)
- [ ] Redis caching layer
- [ ] Queue system (Celery/RQ)
- [ ] Horizontal scaling support
- [ ] CDN integration
- [ ] Multi-region deployment
- [ ] Advanced monitoring and alerting

---

## 📝 Development Notes

### Code Quality
- Type hints used throughout Python codebase
- Pydantic for request/response validation
- Comprehensive error handling
- Structured logging
- SQL injection prevention (parameterized queries)
- XSS protection (HTML escaping)

### Testing
- Unit tests for core business logic
- Integration tests for API endpoints
- End-to-end tests for critical flows
- Test coverage target: 80%

### Performance
- Database indexing on frequently queried fields
- Query optimization with SQLAlchemy
- Pagination for large datasets
- Async/await for I/O operations
- Background tasks for email sending

### Monitoring
- Structured logging to files and console
- Request/response logging with timing
- Error tracking and alerting
- Usage metrics collection
- Performance monitoring

---

## 👥 Team & Contributors

**Project Lead**: Development Team  
**Backend Development**: Python/FastAPI specialists  
**Frontend Development**: React/Next.js developers  
**DevOps**: Deployment and infrastructure team  

---

## 📄 License

Commercial License - All Rights Reserved  
Copyright © 2026 ColdEdge Email Service

---

## 🆘 Support

- **Documentation**: `/docs` endpoint
- **API Reference**: `/docs` (Swagger UI)
- **Email**: support@example.com
- **Status Page**: Coming soon

---

**Last Updated**: January 29, 2026  
**Project Status**: ✅ Production Ready  
**Current Version**: 1.0.0
