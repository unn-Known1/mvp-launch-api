"""
Database configuration and session management.
"""

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _get_database_url() -> str:
    """Get database URL from environment variable. Raises error if not set in production."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        environment = os.getenv("ENVIRONMENT", "development")
        if environment == "production":
            raise ValueError(
                "DATABASE_URL environment variable is required in production. "
                "Please set it before starting the application."
            )
        # In development, provide clear error message instead of fallback
        raise ValueError(
            "DATABASE_URL environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    return db_url


DATABASE_URL = _get_database_url()

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
