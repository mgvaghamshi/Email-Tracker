"""
Basic tests for EmailTracker API
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database.connection import Base, get_db
from app.dependencies import get_api_key

# Test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create test database
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def override_get_api_key():
    return "test_api_key"

# Override dependencies
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_api_key] = override_get_api_key

client = TestClient(app)

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_root_endpoint():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "EmailTracker API" in response.json()["message"]

def test_create_api_key():
    """Test API key creation"""
    response = client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "Test API Key",
            "requests_per_minute": 100,
            "requests_per_day": 1000
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test API Key"
    assert "key" in data  # API key should be returned

def test_send_email():
    """Test email sending"""
    response = client.post(
        "/api/v1/emails/send",
        json={
            "to_email": "test@example.com",
            "from_email": "sender@test.com",
            "from_name": "Test Sender",
            "subject": "Test Email",
            "html_content": "<h1>Test</h1>",
            "text_content": "Test"
        }
    )
    assert response.status_code == 202
    data = response.json()
    assert data["success"] == True
    assert "tracker_id" in data
    assert "campaign_id" in data

def test_list_trackers():
    """Test listing email trackers"""
    response = client.get("/api/v1/emails/trackers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_bot_detection_debug():
    """Test bot detection debug endpoint"""
    response = client.get(
        "/api/v1/track/debug/bot-detection",
        params={"user_agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_bot"] == True
    assert "googlebot" in data["bot_reason"]

def test_analytics_summary():
    """Test analytics summary"""
    response = client.get("/api/v1/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "emails" in data
    assert "engagement" in data

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
