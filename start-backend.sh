#!/bin/bash

# ColdEdge Email Service - Backend Startup Script
# This script activates the Python virtual environment and starts the backend server

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "❌ Virtual environment not found at $SCRIPT_DIR/.venv"
    echo "Please run: python -m venv .venv"
    exit 1
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source "$SCRIPT_DIR/.venv/bin/activate"

# Check if dependencies are installed
if ! python -c "import fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Start the server
echo "🚀 Starting ColdEdge Email Service Backend..."
echo "📍 Server will be available at: http://localhost:8001"
echo "📚 API Documentation: http://localhost:8001/docs"
echo ""
python "$SCRIPT_DIR/run.py"
