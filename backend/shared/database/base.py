"""
Nepal School Management System - Database Base Configuration
SQLAlchemy 2.0 Async Engine and Session
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

from shared.config.settings import settings

# Reuse database connections in every environment. NullPool made each local API
# request pay for a fresh PostgreSQL connection and TLS/authentication handshake.
engine_options = {
    "echo": settings.database_echo,
    "pool_pre_ping": True,
    "pool_size": settings.database_pool_size,
    "max_overflow": settings.database_max_overflow,
    "pool_timeout": settings.database_pool_timeout_seconds,
    "pool_recycle": settings.database_pool_recycle_seconds,
    "pool_use_lifo": True,
    "connect_args": {
        "command_timeout": settings.database_command_timeout_seconds,
        "server_settings": {"application_name": "nepal-sms"},
    },
}

engine = create_async_engine(settings.database_url, **engine_options)

# Create async session factory
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Declarative Base
Base = declarative_base()


# Dependency for FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Database session dependency for FastAPI endpoints.

    Usage:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_maker() as session:
        try:
            yield session
            # Some services intentionally flush batched SQL and let the request
            # boundary own the transaction, so commit centrally on success.
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Context manager for database sessions (for non-FastAPI usage)
class DatabaseSession:
    """
    Context manager for database sessions.

    Usage:
        async with DatabaseSession() as db:
            result = await db.execute(query)
    """

    def __init__(self):
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        self.session = async_session_maker()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.session.rollback()
        else:
            await self.session.commit()
        await self.session.close()


# Initialize database (create all tables)
async def init_db():
    """Initialize database - create all tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Close database connections
async def close_db():
    """Close all database connections"""
    await engine.dispose()
