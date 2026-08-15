"""Async SQLAlchemy 2.0 engine + session (DB-agnostic: SQLite dev, Postgres prod)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False, future=True, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def init_models() -> None:
    """Create tables for local dev (production uses Alembic migrations)."""
    from app import models  # noqa: F401  (register mappers)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
