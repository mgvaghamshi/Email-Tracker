#!/bin/bash

# Render deployment startup script for EmailTracker API

set -e  # Exit on any error

echo "🚀 Starting EmailTracker API on Render..."
echo "Environment: ${ENVIRONMENT:-production}"
echo "Port: ${PORT:-8001}"

# Install dependencies if needed
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Initialize database if needed
echo "📊 Initializing database..."
python3 run.py --init-db || echo "Database already initialized"

# Start the application
echo "🌟 Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}
