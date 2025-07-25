"""
Simple entry point for Render deployment
Render auto-detects this file and runs it
"""

import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from app.main import app

# This is what Render will run
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment (Render sets this)
    port = int(os.environ.get("PORT", 8001))
    
    print(f"🚀 Starting EmailTracker API on port {port}")
    
    # Initialize database
    try:
        from app.database.connection import init_db
        print("📊 Initializing database...")
        init_db()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
        # Continue anyway - might be already initialized
    
    # Start the server
    print("🌟 Starting FastAPI server...")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
