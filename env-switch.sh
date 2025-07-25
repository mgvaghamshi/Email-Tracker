#!/bin/bash

# Environment Management Script for EmailTracker API
# Usage: ./env-switch.sh [development|staging|production]

ENV=${1:-development}
ENV_FILE=".env"

echo "🔧 EmailTracker Environment Manager"
echo "=================================="

case $ENV in
    "development"|"dev")
        echo "🛠️  Switching to DEVELOPMENT environment..."
        cp .env.example $ENV_FILE 2>/dev/null || echo "⚠️  .env.example not found, using current .env"
        echo "ENVIRONMENT=development" > $ENV_FILE.tmp
        echo "DEBUG=true" >> $ENV_FILE.tmp
        echo "BASE_URL=http://localhost:8001" >> $ENV_FILE.tmp
        grep -v "^ENVIRONMENT=\|^DEBUG=\|^BASE_URL=" $ENV_FILE >> $ENV_FILE.tmp 2>/dev/null
        mv $ENV_FILE.tmp $ENV_FILE
        echo "✅ Development environment configured"
        ;;
    
    "staging"|"stage")
        echo "🚧 Switching to STAGING environment..."
        if [ -f ".env.staging" ]; then
            cp .env.staging $ENV_FILE
            echo "✅ Staging environment configured"
        else
            echo "❌ .env.staging file not found"
            exit 1
        fi
        ;;
    
    "production"|"prod")
        echo "🚀 Switching to PRODUCTION environment..."
        if [ -f ".env.production" ]; then
            cp .env.production $ENV_FILE
            echo "✅ Production environment configured"
            echo ""
            echo "⚠️  IMPORTANT PRODUCTION CHECKLIST:"
            echo "   - Update SECRET_KEY with a secure random string"
            echo "   - Configure production database (PostgreSQL)"
            echo "   - Set up production SMTP credentials"
            echo "   - Review CORS origins"
            echo "   - Set DEBUG=false"
            echo "   - Configure monitoring (Sentry)"
        else
            echo "❌ .env.production file not found"
            exit 1
        fi
        ;;
    
    *)
        echo "❌ Invalid environment: $ENV"
        echo "Usage: $0 [development|staging|production]"
        exit 1
        ;;
esac

echo ""
echo "🔍 Current configuration:"
echo "Environment: $(grep '^ENVIRONMENT=' $ENV_FILE | cut -d'=' -f2)"
echo "Debug: $(grep '^DEBUG=' $ENV_FILE | cut -d'=' -f2)"
echo "Base URL: $(grep '^BASE_URL=' $ENV_FILE | cut -d'=' -f2)"
echo "Database: $(grep '^DATABASE_URL=' $ENV_FILE | cut -d'=' -f2 | cut -d':' -f1)"

echo ""
echo "📋 Next steps:"
echo "1. Review and update .env file if needed"
echo "2. Restart the service: python3 run.py --reload"
echo "3. Test the API: curl http://localhost:8001/health"
echo ""
echo "📚 Documentation: docs/ENVIRONMENT_SETUP.md"
