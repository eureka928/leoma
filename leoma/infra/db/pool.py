"""Async database connection pool and session management."""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from leoma.bootstrap import emit_log
from leoma.infra.db.tables import Base

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() == "true"


def _ensure_asyncpg(url: str) -> str:
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _build_url_from_components() -> str:
    from leoma.bootstrap import (
        POSTGRES_DB,
        POSTGRES_HOST,
        POSTGRES_PASSWORD,
        POSTGRES_PORT,
        POSTGRES_USER,
    )
    return (
        "postgresql+asyncpg://"
        f"{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


_DEFAULT_POSTGRES_PASSWORD = "leoma"


def fetch_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return _ensure_asyncpg(url)
    # In production, require DATABASE_URL or explicit non-default password
    env = os.environ.get("LEOMA_ENV", os.environ.get("ENVIRONMENT", "")).lower()
    if env == "production":
        password = os.environ.get("POSTGRES_PASSWORD", _DEFAULT_POSTGRES_PASSWORD)
        if password == _DEFAULT_POSTGRES_PASSWORD:
            raise RuntimeError(
                "Production requires DATABASE_URL or a non-default POSTGRES_PASSWORD. "
                "Set DATABASE_URL or POSTGRES_PASSWORD to avoid using the default."
            )
    return _build_url_from_components()


def _session_factory_or_raise() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_factory


async def init_database(database_url: Optional[str] = None) -> AsyncEngine:
    global _engine, _session_factory
    if _engine is not None:
        return _engine
    if database_url is None:
        database_url = fetch_database_url()
    emit_log("Initializing database connection", "info")
    _engine = create_async_engine(
        database_url,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=_env_flag("DATABASE_ECHO"),
    )
    _session_factory = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )
    emit_log("Database connection pool initialized", "success")
    return _engine


async def close_database() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        emit_log("Database connection pool closed", "info")


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = _session_factory_or_raise()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def create_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    emit_log("Database tables created", "success")


async def drop_tables() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    emit_log("Database tables dropped", "warn")
