# Environment Configuration Guide

This document explains how to configure the EmailTracker API for different environments.

## Environment Files

- `.env` - Development environment (default)
- `.env.staging` - Staging environment 
- `.env.production` - Production environment

## Quick Setup

### Development Setup
```bash
# Use the default .env file
cp .env.example .env
# Edit .env with your development settings
```

### Staging Setup
```bash
# Copy staging template
cp .env.staging .env
# Edit with your staging configuration
```

### Production Setup
```bash
# Copy production template
cp .env.production .env
# Edit with your production configuration
```

## Configuration Sections

### 1. Core Application Settings
- `ENVIRONMENT`: Set to development/staging/production
- `BASE_URL`: Your API's base URL
- `SECRET_KEY`: **CRITICAL** - Use a long, random string in production
- `DEBUG`: Enable/disable debug mode

### 2. Database Configuration
- **Development**: SQLite (file-based)
- **Staging/Production**: PostgreSQL (recommended)
- Connection pooling settings for performance

### 3. Email Service Configuration
- **Development**: Gmail SMTP or Mailtrap
- **Staging**: Mailtrap or sandbox mode
- **Production**: Production SMTP, SendGrid, Mailgun, or AWS SES

### 4. Redis Configuration
- Required for task queues and caching
- **Development**: Local Redis
- **Production**: Redis with authentication

### 5. Security Settings
- CORS origins (restrict in production)
- Rate limiting
- Security headers
- API key rate limits

### 6. Monitoring & Analytics
- Sentry for error tracking
- Google Analytics integration
- Custom analytics retention

### 7. Feature Flags
- Enable/disable specific features
- Useful for gradual rollouts

## Security Checklist

### Development ✓
- [x] Basic authentication
- [x] Local database
- [x] Permissive CORS
- [x] Debug logging enabled

### Production ⚠️
- [ ] **Change SECRET_KEY** to a secure random string
- [ ] Use PostgreSQL database
- [ ] Configure production SMTP
- [ ] Restrict CORS origins to your domains
- [ ] Set DEBUG=false
- [ ] Use HTTPS only
- [ ] Configure proper logging
- [ ] Set up monitoring (Sentry)
- [ ] Review and configure rate limits

## Environment Variables Priority

1. System environment variables (highest priority)
2. `.env` file
3. Default values in code (lowest priority)

## Production Deployment

### Docker Deployment
```bash
# Build with production environment
docker build -t emailtracker-api .

# Run with production environment file
docker run -d \
  --env-file .env.production \
  -p 8001:8001 \
  emailtracker-api
```

### Traditional Deployment
```bash
# Copy production environment
cp .env.production .env

# Install dependencies
pip install -r requirements.txt

# Run migrations
python3 run.py --init-db

# Start production server
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Monitoring & Health Checks

### Health Check Endpoint
```
GET /health
```

### Metrics & Analytics
- Email delivery rates
- API response times
- Error rates
- Campaign performance

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check DATABASE_URL format
   - Verify database server is running
   - Check network connectivity

2. **Email Sending Failures**
   - Verify SMTP credentials
   - Check firewall/network settings
   - Test with email service provider's sandbox

3. **Redis Connection Issues**
   - Verify Redis server is running
   - Check REDIS_URL format
   - Verify authentication if required

4. **High Memory Usage**
   - Adjust database pool settings
   - Review worker configuration
   - Check for memory leaks in custom code

## Support

For additional support:
- Check the application logs
- Review the API documentation at `/docs`
- Monitor health checks
- Use the debug endpoints in development
