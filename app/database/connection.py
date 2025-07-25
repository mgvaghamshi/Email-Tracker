"""
Database connection and initialization
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from ..config import settings


# Create SQLAlchemy engine
engine = create_engine(
    settings.database_url,
    # SQLite specific configurations
    connect_args={
        "check_same_thread": False,
        "timeout": 30
    } if "sqlite" in settings.database_url else {},
    # Connection pooling for SQLite
    poolclass=StaticPool if "sqlite" in settings.database_url else None,
    echo=settings.debug
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for models
Base = declarative_base()


def init_db():
    """Initialize database tables"""
    # Import all models to ensure they are registered
    from .models import EmailTracker, EmailEvent, EmailBounce, EmailClick, ApiKey
    
    # Create all tables
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
