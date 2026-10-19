from __future__ import annotations

import asyncio
import selectors
import sys
from collections.abc import Coroutine
from typing import Any


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine on an event loop psycopg can use.

    On Windows the default ProactorEventLoop cannot run psycopg in async mode,
    so we use a SelectorEventLoop there. Everywhere else, plain asyncio.run.
    """
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    return asyncio.run(coro)
