from collections.abc import AsyncIterator
from ssl import create_default_context
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from medivault.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

_TLS_MODES = {"require", "verify-ca", "verify-full"}


def build_ssl_connect_args() -> dict[str, Any]:
    mode = get_settings().database_ssl_mode()
    if mode in _TLS_MODES:
        return {"ssl": create_default_context()}
    if mode == "disable":
        return {"ssl": False}
    return {}


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().require_database_url(),
            connect_args=build_ssl_connect_args(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), expire_on_commit=False, autoflush=False
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_session_factory()() as session:
        yield session


def reset_database_state() -> None:
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def dispose_engine_if_created() -> None:
    """Dispose the engine if it exists (used by tests: one engine per event loop)."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
