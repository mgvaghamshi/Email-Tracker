#!/usr/bin/env python3
"""
EmailTracker API startup script
"""
import os
import sys
import argparse
import uvicorn
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.database.connection import init_db

def main():
    parser = argparse.ArgumentParser(description="EmailTracker API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--init-db", action="store_true", help="Initialize database and exit")
    
    args = parser.parse_args()
    
    if args.init_db:
        print("🔧 Initializing database...")
        try:
            init_db()
            print("✅ Database initialized successfully!")
        except Exception as e:
            print(f"❌ Database initialization failed: {e}")
            sys.exit(1)
        return
    
    print("🚀 Starting EmailTracker API...")
    print(f"📍 Host: {args.host}")
    print(f"🔌 Port: {args.port}")
    print(f"🔧 Debug: {args.debug or settings.debug}")
    print(f"🔄 Reload: {args.reload}")
    print(f"📊 Base URL: {settings.base_url}")
    
    # Initialize database on startup
    try:
        init_db()
        print("✅ Database ready")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        sys.exit(1)
    
    # Start the server
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if (args.debug or settings.debug) else "info",
        access_log=True
    )

if __name__ == "__main__":
    main()
