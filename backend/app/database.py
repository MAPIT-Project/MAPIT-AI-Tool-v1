from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
from .models import Base
import asyncio
from contextlib import asynccontextmanager

from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.engine import URL
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Database configuration
POSTGRES_USER = os.getenv("POSTGRES_USER", "mapit_user")
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
POSTGRES_DB = os.getenv("POSTGRES_DB", "mapit_chat")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")

# Database URL
DATABASE_URL = URL.create("postgresql", username=POSTGRES_USER, password=POSTGRES_PASSWORD, host=POSTGRES_HOST, port=int(POSTGRES_PORT), database=POSTGRES_DB)

# Create engine with increased pool size for 5-10 concurrent users
engine = create_engine(
    DATABASE_URL,
    pool_size=25,  # Increased from 10 to 25
    max_overflow=50,  # Increased from 20 to 50
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo=False  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

# Async database session manager
@asynccontextmanager
async def get_async_db():
    """Async database session manager for non-blocking operations"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except:
        db.rollback()
        raise
    finally:
        db.close()

# Create tables
def create_tables():
    Base.metadata.create_all(bind=engine)

# Check database connection
def check_database_connection():
    try:
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db.close()
        return {
            "status": "healthy", 
            "message": "Database connection successful",
            "context_status": "ready"
        }
    except Exception as e:
        # Don't raise the exception, just return the error status
        return {
            "status": "unhealthy", 
            "message": f"Database connection failed: {str(e)}",
            "context_status": "error"
        } 