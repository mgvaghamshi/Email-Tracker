"""
Database connection and initialization with performance optimizations
"""
from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool, QueuePool
from sqlalchemy.engine import Engine
import sqlite3

from ..config import settings


def sqlite_performance_tuning(dbapi_connection, connection_record):
    """Apply SQLite performance optimizations"""
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        # Enable WAL mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        # Increase cache size (negative value means KB)
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        # Enable query optimization
        cursor.execute("PRAGMA optimize")
        # Faster synchronization
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Memory-mapped I/O
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        # Temp store in memory
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.close()


# Create optimized SQLAlchemy engine
if "sqlite" in settings.database_url:
    engine = create_engine(
        settings.database_url,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
            "isolation_level": None,  # Autocommit mode
        },
        poolclass=StaticPool,
        pool_pre_ping=True,
        pool_recycle=3600,  # Recycle connections every hour
        echo=settings.debug
    )
    # Apply SQLite performance tuning
    event.listen(engine, "connect", sqlite_performance_tuning)
else:
    # PostgreSQL/MySQL optimizations
    engine = create_engine(
        settings.database_url,
        poolclass=QueuePool,
        pool_size=20,  # Larger connection pool
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=settings.debug
    )

# Create optimized SessionLocal class
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,  # Manual flush for better control
    bind=engine,
    expire_on_commit=False  # Keep objects usable after commit
)

# Create Base class for models
Base = declarative_base()


def init_db():
    """Initialize database tables with performance optimizations"""
    # Import all models to ensure they are registered
    from .models import EmailTracker, EmailEvent, EmailBounce, EmailClick, Campaign, Contact, Template
    from .user_models import ApiKey, User, Role, UserRole, ApiKeyUsage
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    # Create additional performance indexes if using SQLite
    if "sqlite" in settings.database_url:
        with engine.connect() as conn:
            # Additional performance indexes for frequent queries
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_user_campaigns 
                ON campaigns(user_id, status, created_at DESC)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_email_analytics 
                ON email_trackers(campaign_id, delivered, open_count > 0, click_count > 0)
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_performance_user_analytics 
                ON email_trackers(user_id, created_at, delivered)
            """))
            conn.commit()


def get_db():
    """Get database session with optimized settings"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_sync():
    """Get synchronous database session for background tasks"""
    return SessionLocal()
