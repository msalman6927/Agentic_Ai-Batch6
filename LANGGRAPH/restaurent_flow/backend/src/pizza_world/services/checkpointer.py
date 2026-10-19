from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import cast

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from pizza_world.config import settings

_cm: AbstractAsyncContextManager[AsyncPostgresSaver] | None = None
_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Lazy singleton AsyncPostgresSaver; checkpoint tables created via setup()."""
    global _cm, _checkpointer
    if _checkpointer is None:
        _cm = cast(
            "AbstractAsyncContextManager[AsyncPostgresSaver]",
            AsyncPostgresSaver.from_conn_string(settings.psycopg_dsn),
        )
        _checkpointer = await _cm.__aenter__()
        await _checkpointer.setup()
    return _checkpointer


async def aclose_checkpointer() -> None:
    global _cm, _checkpointer
    if _cm is not None:
        await _cm.__aexit__(None, None, None)
        _cm = None
        _checkpointer = None
