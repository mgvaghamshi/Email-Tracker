# Docker Deployment Guide

## 🐳 Docker Setup for EmailTracker API

This guide covers deploying the EmailTracker API using Docker and Docker Compose.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 2GB available RAM
- 5GB available disk space

## 🚀 Quick Start

### 1. Basic Deployment (API + Database + Redis)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f api

# Check service status
docker-compose ps
```

### 2. With Nginx Reverse Proxy
```bash
# Start with Nginx
docker-compose --profile with-nginx up -d

# Access via Nginx
curl http://localhost/health
```

### 3. Production Deployment
```bash
# Copy production environment
cp .env.production .env.docker

# Edit configuration
nano .env.docker

# Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│     Nginx       │    │  EmailTracker   │    │   PostgreSQL    │
│ (Reverse Proxy) │───▶│      API        │───▶│    Database     │
│   Port: 80/443  │    │   Port: 8001    │    │   Port: 5432    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │      Redis      │
                       │ (Cache/Queue)   │
                       │   Port: 6379    │
                       └─────────────────┘
```

## 📁 Docker Files Structure

```
emailtracker/
├── Dockerfile                 # Main API container
├── docker-compose.yml        # Multi-service setup
├── .env.docker              # Docker environment config
├── init-db.sql              # PostgreSQL initialization
├── nginx/
│   └── nginx.conf           # Nginx configuration
└── docs/
    └── DOCKER_SETUP.md      # This documentation
```

## 🔧 Service Configuration

### API Service (emailtracker-api)
- **Image**: Custom built from Dockerfile
- **Port**: 8001
- **Environment**: PostgreSQL + Redis
- **Health Check**: `/health` endpoint
- **Auto-restart**: Unless stopped

### Database Service (emailtracker-db)
- **Image**: postgres:15-alpine
- **Port**: 5432
- **Volume**: Persistent PostgreSQL data
- **Init Script**: `init-db.sql`
- **Health Check**: pg_isready

### Redis Service (emailtracker-redis)
- **Image**: redis:7-alpine
- **Port**: 6379
- **Volume**: Persistent Redis data
- **Health Check**: redis-cli ping

### Nginx Service (emailtracker-nginx)
- **Image**: nginx:alpine
- **Ports**: 80, 443
- **Config**: Custom reverse proxy
- **Profile**: `with-nginx` (optional)

## 🗄️ Data Persistence

### Volumes
- `postgres_data`: PostgreSQL database files
- `redis_data`: Redis persistence files
- `./logs`: Application logs (mounted)

### Backup Strategy
```bash
# Backup PostgreSQL
docker-compose exec db pg_dump -U postgres email_tracker > backup.sql

# Restore PostgreSQL
docker-compose exec -T db psql -U postgres email_tracker < backup.sql

# Backup Redis
docker-compose exec redis redis-cli BGSAVE
```

## 🔒 Security Configuration

### Environment Variables
```bash
# Required for production
SECRET_KEY=your-secure-secret-key-here
DATABASE_URL=postgresql://user:pass@db:5432/email_tracker
ENVIRONMENT=production
DEBUG=false

# Optional security
CORS_ORIGINS=["https://yourdomain.com"]
RATE_LIMIT_REQUESTS=1000
```

### Network Security
- Internal Docker network for service communication
- Only necessary ports exposed to host
- Nginx rate limiting configured
- Health checks for all services

## 📊 Monitoring & Logging

### Health Checks
```bash
# API health
curl http://localhost:8001/health

# Database health
docker-compose exec db pg_isready -U postgres

# Redis health
docker-compose exec redis redis-cli ping

# Nginx health
curl http://localhost/nginx-health
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f db
docker-compose logs -f redis
docker-compose logs -f nginx

# Follow logs with timestamps
docker-compose logs -f -t api
```

## 🔧 Development Setup

### Hot Reload Development
```bash
# Start with volume mounting for development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Access API with hot reload
curl http://localhost:8001/docs
```

### Database Management
```bash
# Access PostgreSQL shell
docker-compose exec db psql -U postgres email_tracker

# Run migrations
docker-compose exec api python3 run.py --init-db

# Reset database
docker-compose down -v
docker-compose up -d
```

## 🚀 Production Deployment

### 1. Environment Setup
```bash
# Copy and configure production environment
cp .env.production .env.docker

# Update critical settings
nano .env.docker
```

### 2. SSL/TLS Setup (with Nginx)
```bash
# Create SSL directory
mkdir -p nginx/ssl

# Add your SSL certificates
cp your-cert.pem nginx/ssl/cert.pem
cp your-key.pem nginx/ssl/key.pem

# Enable HTTPS in nginx.conf
nano nginx/nginx.conf
```

### 3. Production Deployment
```bash
# Deploy to production
docker-compose --profile with-nginx up -d

# Verify deployment
curl https://yourdomain.com/health
```

## 🔍 Troubleshooting

### Common Issues

1. **Port Already in Use**
   ```bash
   # Check what's using the port
   lsof -i :8001
   
   # Stop conflicting services
   docker-compose down
   ```

2. **Database Connection Error**
   ```bash
   # Check database status
   docker-compose exec db pg_isready -U postgres
   
   # Restart database
   docker-compose restart db
   ```

3. **Permission Errors**
   ```bash
   # Fix file permissions
   chmod +x run.py
   sudo chown -R 1000:1000 logs/
   ```

4. **Memory Issues**
   ```bash
   # Check container resource usage
   docker stats
   
   # Restart services
   docker-compose restart
   ```

### Debug Commands
```bash
# Access API container
docker-compose exec api bash

# Check environment variables
docker-compose exec api env | grep -E "(DATABASE|REDIS|ENVIRONMENT)"

# Test internal connectivity
docker-compose exec api curl http://db:5432
docker-compose exec api curl http://redis:6379
```

## 📈 Performance Optimization

### Production Tuning
```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 1G
          cpus: '0.5'
        reservations:
          memory: 512M
          cpus: '0.25'
```

### Scaling
```bash
# Scale API instances
docker-compose up -d --scale api=3

# Load balance with Nginx
# (Nginx config automatically load balances)
```

## 🆘 Support Commands

```bash
# Complete reset
docker-compose down -v --remove-orphans
docker system prune -a

# Update images
docker-compose pull
docker-compose up -d --force-recreate

# Export logs
docker-compose logs --no-color > emailtracker-logs.txt
```
