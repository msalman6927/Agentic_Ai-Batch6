from uuid import UUID

from fastapi import APIRouter

from medivault.schemas.chat import (
    CitationOut,
    ConversationListOut,
    ConversationOut,
    MessageDetailOut,
    MessageListOut,
)
from medivault.services import conversation_service

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListOut)
async def list_conversations() -> ConversationListOut:
    conversations = await conversation_service.list_conversations()
    return ConversationListOut(
        items=[ConversationOut.model_validate(item) for item in conversations]
    )


@router.get("/{conversation_id}/messages", response_model=MessageListOut)
async def get_conversation_messages(conversation_id: UUID) -> MessageListOut:
    messages = await conversation_service.get_messages(conversation_id)
    items: list[MessageDetailOut] = []
    for message in messages:
        citations = await conversation_service.get_citations(message.id)
        detail = MessageDetailOut.model_validate(message)
        detail.citations = [
            CitationOut(
                source_type=citation.source_type,
                title=citation.title,
                snippet=citation.snippet,
                score=citation.score,
                rank=citation.rank,
            )
            for citation in citations
        ]
        items.append(detail)
    return MessageListOut(items=items)
