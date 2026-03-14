"""
Database Configuration
Async SQLAlchemy setup with session management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# Create async engine
settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    # SQLite specific settings
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Increase timeout to 30 seconds
    } if settings.is_sqlite else {},
    # Pool settings to prevent premature connection closure
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session with automatic cleanup."""
    session = async_session_factory()
    try:
        yield session
        # Only commit if session is still active
        if session.is_active:
            await session.commit()
    except Exception:
        # Only rollback if session is still active
        if session.is_active:
            await session.rollback()
        raise
    finally:
        # Always close, but handle if already closed
        try:
            await session.close()
        except Exception:
            pass  # Session already closed, ignore


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI route injection."""
    async with get_session() as session:
        yield session
