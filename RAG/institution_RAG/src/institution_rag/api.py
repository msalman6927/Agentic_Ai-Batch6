from typing import Literal
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from institution_rag.chat import stream_reply
from institution_rag.config import HISTORY_LIMIT, MAX_MESSAGE_CHARS
from institution_rag.store import connect

app = FastAPI(title="institution-rag-chat", version="0.1.0")

CONVERSATIONS: dict[str, list[dict[str, str]]] = {}

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content must not be blank")
        return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    conversation_id: UUID | None = None
    history: list[ChatMessage] | None = Field(default=None, max_length=HISTORY_LIMIT)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value.strip()


@app.post("/chat")
def chat(request: ChatRequest) -> StreamingResponse:
    conversation_id = str(request.conversation_id or uuid4())
    if request.history is not None:
        CONVERSATIONS[conversation_id] = [
            {"role": message.role, "content": message.content}
            for message in request.history
        ]
    messages = CONVERSATIONS.setdefault(conversation_id, [])
    return StreamingResponse(
        stream_reply(
            message=request.message,
            conversation_id=conversation_id,
            messages=messages,
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/health")
def health() -> dict:
    try:
        with connect() as conn:
            conn.execute("SELECT 1")
        database = "ok"
    except Exception as exc:  # noqa: BLE001
        database = f"error: {type(exc).__name__}: {exc}"
    return {"status": "ok", "database": database}
