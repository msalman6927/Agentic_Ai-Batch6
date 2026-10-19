"""In-process asyncio pub/sub for SSE fan-out.

Single-process only (run uvicorn without --workers). Upgrade path: Postgres LISTEN/NOTIFY.
Topics: "user:{user_id}", "admin", "kitchen".
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any


def user_topic(user_id: str) -> str:
    return f"user:{user_id}"


ADMIN_TOPIC = "admin"
KITCHEN_TOPIC = "kitchen"


class EventBus:
    def __init__(self) -> None:
        self._topics: dict[str, set[asyncio.Queue[dict[str, Any]]]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._topics.setdefault(topic, set()).add(q)
        return q

    def unsubscribe(self, topic: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._topics.get(topic)
        if subs is None:
            return
        subs.discard(q)
        if not subs:
            self._topics.pop(topic, None)

    async def publish(self, topic: str, event: dict[str, Any]) -> None:
        for q in list(self._topics.get(topic, ())):
            with contextlib.suppress(Exception):
                q.put_nowait(event)

    async def publish_many(self, topics: list[str], event: dict[str, Any]) -> None:
        for topic in topics:
            await self.publish(topic, event)


bus = EventBus()
