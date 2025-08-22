from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from src.core.settings import settings
import logging

logger = logging.getLogger(__name__)

# Create async engine with conditional pooling
engine_kwargs = {
    "echo": settings.debug,
    "future": True,
}

# Only add pooling parameters for non-SQLite databases
if not settings.database_url.startswith("sqlite"):
    engine_kwargs.update({
        "pool_size": settings.database_pool_max_size,
        "max_overflow": settings.database_pool_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 3600,  # Recycle connections every hour
    })

engine = create_async_engine(settings.database_url, **engine_kwargs)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

