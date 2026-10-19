from __future__ import annotations

from pizza_world.db.models import ChatMessage
from pizza_world.db.session import get_session_maker


async def save_message(*, thread_id: str, user_id: str, role: str, content: str) -> None:
    async with get_session_maker()() as session:
        session.add(ChatMessage(thread_id=thread_id, user_id=user_id, role=role, content=content))
        await session.commit()


async def get_thread_messages(
    *, thread_id: str, user_id: str, limit: int = 200
) -> list[ChatMessage]:
    from sqlalchemy import select

    async with get_session_maker()() as session:
        rows = (
            (
                await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread_id, ChatMessage.user_id == user_id)
                    .order_by(ChatMessage.created_at)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)
