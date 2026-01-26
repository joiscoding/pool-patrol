"""Database connection and session management for Pool Patrol.

This module provides SQLAlchemy database connectivity that works with
both SQLite (development) and PostgreSQL (production).

Usage:
    from pool_patrol_core.database import get_session, init_db
    
    # Initialize database (creates tables if needed)
    init_db()
    
    # Use session for queries
    with get_session() as session:
        employees = session.query(Employee).all()
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base

# Base class for SQLAlchemy models
Base = declarative_base()

# Default to SQLite in development
# Set DATABASE_URL environment variable to use PostgreSQL
DEFAULT_DATABASE_URL = f"sqlite:///{Path(__file__).parent.parent.parent.parent / 'prisma' / 'dev.db'}"


def get_database_url() -> str:
    """Get database URL from environment or use default SQLite."""
    url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    
    # Prisma uses "file:" prefix for SQLite, SQLAlchemy uses "sqlite:///"
    if url.startswith("file:"):
        # Convert Prisma-style path to SQLAlchemy-style
        path = url.replace("file:", "")
        if path.startswith("./"):
            # Relative path - make it absolute from prisma directory
            path = str(Path(__file__).parent.parent.parent.parent / "prisma" / path[2:])
        url = f"sqlite:///{path}"
    
    return url


# Create engine (lazy initialization)
_engine = None
_SessionLocal = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    if _engine is None:
        database_url = get_database_url()
        
        # SQLite-specific settings
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        
        _engine = create_engine(
            database_url,
            connect_args=connect_args,
            echo=os.environ.get("SQL_DEBUG", "").lower() == "true",
        )
    return _engine


def get_session_factory():
    """Get or create the session factory."""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Get a database session as a context manager.
    
    Usage:
        with get_session() as session:
            employees = session.query(Employee).all()
    """
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize the database (create tables if they don't exist).
    
    Note: In production, use Prisma migrations instead.
    This is mainly for testing or development convenience.
    """
    # Import models to register them with Base
    from pool_patrol_core.db_models import (
        Vanpool, Employee, Rider, Case, EmailThread, Message
    )
    Base.metadata.create_all(bind=get_engine())


def reset_engine():
    """Reset the engine and session factory (useful for testing)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
