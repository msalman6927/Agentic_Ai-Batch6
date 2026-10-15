from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from medivault.config import get_settings


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: UUID | None = None
    patient_id: UUID | None = Field(
        default=None,
        description="Optional: focus the agent on this patient from the first turn",
    )

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        limit = get_settings().max_message_chars
        if not cleaned:
            raise ValueError("message must not be blank")
        if len(cleaned) > limit:
            raise ValueError(f"message exceeds {limit} characters")
        return cleaned


class CitationOut(BaseModel):
    source_type: str
    title: str | None = None
    snippet: str
    score: float
    rank: int


class MessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    confidence: float | None = None
    from_vault: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageDetailOut(MessageOut):
    citations: list[CitationOut] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: UUID
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationListOut(BaseModel):
    items: list[ConversationOut]


class MessageListOut(BaseModel):
    items: list[MessageDetailOut]


RoleLiteral = Literal["user", "assistant", "system"]
