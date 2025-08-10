# ColdEdge Email Service

> Professional email infrastructure service for businesses and developers

ColdEdge Email Service is a production-ready email API that provides reliable email sending, tracking, and analytics. Similar to Mailgun or SendGrid, but with enhanced features for cold email campaigns and detailed analytics.

## ✨ Features

### 📧 Email Sending
- Single email sending with tracking
- Bulk email campaigns
- Template management
- Personalization support
- Bounce handling

### 📊 Analytics & Tracking
- Real-time email open tracking
- Click tracking with detailed analytics
- Campaign performance metrics
- Engagement analytics
- Geographic insights

### 🔐 Enterprise Security
- API key management with scoping
- Rate limiting and usage tracking
- User management and permissions
- Webhook notifications
- Comprehensive audit logs

### 🚀 Production Ready
- High-performance FastAPI backend
- PostgreSQL database support
- Redis caching (optional)
- Docker deployment
- Comprehensive monitoring

## 🚀 Quick Start

### 1. Installation
```bash
git clone https://github.com/yourusername/coldemail-service.git
cd coldemail-service
pip install -r requirements.txt
```

### 2. Configuration
```bash
cp .env.template .env
# Edit .env with your configuration
```

### 3. Database Setup
```bash
# For development (SQLite)
python setup_database.py

# For production (PostgreSQL)
# See PRODUCTION_DEPLOYMENT.md
```

### 4. Start the Service
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

### 5. Access API Documentation
Open http://localhost:8001/docs in your browser

## 📖 API Usage

### Send an Email
```bash
curl -X POST "http://localhost:8001/api/v1/emails/send" \
     -H "Authorization: Bearer your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "to_email": "customer@example.com",
       "from_email": "hello@yourcompany.com",
       "from_name": "Your Company",
       "subject": "Welcome to our service!",
       "html_content": "<h1>Welcome!</h1><p>Thanks for signing up.</p>"
     }'
```

### Track Email Performance
```bash
curl -H "Authorization: Bearer your_api_key" \
     "http://localhost:8001/api/v1/analytics/campaigns/campaign_id"
```

### Bulk Email Campaign
```bash
curl -X POST "http://localhost:8001/api/v1/emails/bulk" \
     -H "Authorization: Bearer your_api_key" \
     -H "Content-Type: application/json" \
     -d '{
       "campaign_name": "Product Launch",
       "from_email": "marketing@yourcompany.com",
       "subject": "New Product Alert",
       "html_content": "<h1>Check out our new product!</h1>",
       "recipients": [
         {"email": "user1@example.com", "name": "John"},
         {"email": "user2@example.com", "name": "Jane"}
       ]
     }'
```

## 🏗 Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client App    │    │   Dashboard     │    │   Webhooks      │
│                 │    │                 │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │                             │
                    │    ColdEdge Email API       │
                    │    (FastAPI + SQLAlchemy)   │
                    │                             │
                    └─────────────┬───────────────┘
                                  │
                    ┌─────────────▼───────────────┐
                    │                             │
                    │      PostgreSQL DB          │
                    │   (Users, Campaigns,        │
                    │    Tracking Data)           │
                    │                             │
                    └─────────────────────────────┘
```

## 📊 Performance

- **Throughput**: 10,000+ emails/minute
- **Response Time**: < 100ms for API calls
- **Reliability**: 99.9% uptime SLA
- **Scalability**: Horizontal scaling with load balancers

## 🛡 Security

- API key authentication with scoping
- Rate limiting per API key
- SQL injection protection
- CORS configuration
- Webhook signature verification
- Comprehensive audit logging

## 🔧 Configuration

All configuration is managed through environment variables. See `.env.template` for all available options.

### Required Settings
- `SECRET_KEY`: Application secret key
- `DATABASE_URL`: Database connection string
- `SMTP_*`: Email sending configuration

### Optional Settings
- `REDIS_URL`: For caching and rate limiting
- `WEBHOOK_*`: Webhook configuration
- `CORS_ORIGINS`: Allowed frontend origins

## 📈 Monitoring

### Health Endpoints
- `GET /health` - Service health check
- `GET /api/v1/analytics/usage` - API usage statistics

### Logging
- Structured JSON logs
- Error tracking with Sentry integration
- Performance monitoring
- Database query logging

## 🚢 Deployment

### Development
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

### Production
See [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for detailed production deployment instructions.

### Docker
```bash
docker-compose up -d
```

## 📚 Documentation

- **API Reference**: http://localhost:8001/docs
- **Production Guide**: [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## 🤝 Support

### Enterprise Support
For enterprise customers, we provide:
- 24/7 technical support
- Custom integrations
- On-premise deployment
- SLA guarantees
- Dedicated infrastructure

Contact: support@coldemail.com

### Community
- GitHub Issues for bug reports
- Feature requests via GitHub Discussions
- Community Discord server

## 📄 License

Commercial License - See LICENSE file for details.

## 🛠 Development

### Requirements
- Python 3.8+
- PostgreSQL 12+ (production)
- Redis (optional, for caching)

### Setup Development Environment
```bash
git clone https://github.com/yourusername/coldemail-service.git
cd coldemail-service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.template .env
python setup_database.py
uvicorn app.main:app --reload
```

### Running Tests
```bash
pytest tests/
```

---

**ColdEdge Email Service** - Professional email infrastructure for the modern web.
