from uuid import UUID, uuid4

from sqlalchemy import select

from medivault.db.models import (
    Conversation,
    Message,
    MessageCitation,
    MessageToolCall,
)
from medivault.dependencies import get_session_factory
from medivault.retrieval.hybrid import RetrievalHit
from medivault.utils.errors import NotFoundError


async def get_or_create_conversation(
    conversation_id: UUID | None = None, *, title: str | None = None
) -> Conversation:
    factory = get_session_factory()
    async with factory() as session:
        if conversation_id is not None:
            conversation = await session.get(Conversation, conversation_id)
            if conversation is None:
                raise NotFoundError(f"conversation {conversation_id} not found")
            return conversation
        conversation = Conversation(id=uuid4(), title=title)
        session.add(conversation)
        await session.commit()
        await session.refresh(conversation)
        return conversation


async def list_conversations() -> list[Conversation]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.scalars(
            select(Conversation).order_by(Conversation.updated_at.desc())
        )
        return list(rows)


async def add_message(
    *,
    conversation_id: UUID,
    role: str,
    content: str,
    confidence: float | None = None,
    from_vault: bool = True,
) -> Message:
    factory = get_session_factory()
    async with factory() as session:
        message = Message(
            id=uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            confidence=confidence,
            from_vault=from_vault,
        )
        session.add(message)
        conversation = await session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.title = conversation.title or content[:60]
        await session.commit()
        await session.refresh(message)
        return message


async def add_citations(message_id: UUID, hits: list[RetrievalHit]) -> None:
    if not hits:
        return
    factory = get_session_factory()
    async with factory() as session:
        for rank, hit in enumerate(hits, start=1):
            session.add(
                MessageCitation(
                    id=uuid4(),
                    message_id=message_id,
                    source_type=(
                        f"{hit.doc_type}_chunk" if hit.doc_type else "structured"
                    ),
                    title=hit.extras.get("title"),
                    snippet=hit.snippet,
                    score=round(hit.score, 4),
                    rank=rank,
                )
            )
        await session.commit()


async def add_tool_calls(message_id: UUID, audit: list[dict]) -> None:
    if not audit:
        return
    factory = get_session_factory()
    async with factory() as session:
        for entry in audit:
            session.add(
                MessageToolCall(
                    id=uuid4(),
                    message_id=message_id,
                    tool_name=entry.get("tool", "unknown"),
                    args=entry.get("args"),
                    result_summary=(entry.get("summary") or "")[:2000],
                    status=entry.get("status", "ok"),
                )
            )
        await session.commit()


async def get_messages(conversation_id: UUID) -> list[Message]:
    factory = get_session_factory()
    async with factory() as session:
        exists = await session.get(Conversation, conversation_id)
        if exists is None:
            raise NotFoundError(f"conversation {conversation_id} not found")
        rows = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(rows)


async def get_citations(message_id: UUID) -> list[MessageCitation]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.scalars(
            select(MessageCitation)
            .where(MessageCitation.message_id == message_id)
            .order_by(MessageCitation.rank)
        )
        return list(rows)
