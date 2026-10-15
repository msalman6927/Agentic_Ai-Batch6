import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from medivault.agents.graph import get_graph
from medivault.schemas.chat import ChatRequest
from medivault.services import conversation_service
from medivault.services.confidence import compute_confidence
from medivault.services.memory_service import recent_turns, remember_turn
from medivault.utils.sse import SSE_HEADERS, sse_event

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


def _chunk_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content) if content else ""


def _sources_payload(hits: list[Any]) -> list[dict]:
    payload = []
    for rank, hit in enumerate(hits, start=1):
        entry = hit.to_payload()
        entry["rank"] = rank
        payload.append(entry)
    return payload


async def _build_initial_messages(conversation_id, query: str) -> list[Any]:
    history = await recent_turns(conversation_id)
    messages: list[Any] = []
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(content=turn["content"]))
        elif turn["role"] == "assistant":
            messages.append(AIMessage(content=turn["content"]))
    messages.append(HumanMessage(content=query))
    return messages


async def stream_chat(payload: ChatRequest) -> AsyncIterator[str]:
    conversation = await conversation_service.get_or_create_conversation(
        payload.conversation_id, title=payload.message[:60]
    )
    conversation_id = conversation.id
    yield sse_event(
        "meta",
        {
            "conversation_id": str(conversation_id),
            "patient_id": str(payload.patient_id) if payload.patient_id else None,
        },
    )

    initial_messages = await _build_initial_messages(conversation_id, payload.message)
    inputs: dict[str, Any] = {
        "messages": initial_messages,
        "query": payload.message,
        "conversation_id": str(conversation_id),
        "patient_id": str(payload.patient_id) if payload.patient_id else None,
        "hits": [],
        "context_blocks": [],
        "from_vault": True,
        "patient_summary": None,
        "tool_audit": [],
        "pending_writes": [],
    }

    final_text = ""
    hits: list[Any] = []
    audit: list[dict] = []
    pending: list[dict] = []
    try:
        graph = get_graph()
        stream = graph.astream(inputs, stream_mode=["updates", "messages"])
        async for mode, chunk in stream:
            if mode == "messages":
                message_chunk, _metadata = chunk
                text = _chunk_text(getattr(message_chunk, "content", None))
                if text.strip():
                    final_text += text
                    yield sse_event("token", {"text": text})
            elif mode == "updates":
                for node_name, update in chunk.items():
                    if node_name == "retrieve":
                        hits = update.get("hits", hits)
                        yield sse_event("sources", {"sources": _sources_payload(hits)})
                    elif node_name == "agent":
                        messages = update.get("messages", [])
                        if messages:
                            last = messages[-1]
                            for call in getattr(last, "tool_calls", []) or []:
                                yield sse_event(
                                    "tool_call",
                                    {
                                        "tool": call.get("name"),
                                        "args": call.get("args"),
                                        "step": len(audit) + 1,
                                    },
                                )
                    elif node_name == "tools":
                        audit.extend(update.get("tool_audit", []))
                        pending.extend(update.get("pending_writes", []))
                        for entry in update.get("tool_audit", []):
                            yield sse_event(
                                "tool_result",
                                {
                                    "tool": entry.get("tool"),
                                    "summary": entry.get("summary"),
                                    "status": entry.get("status"),
                                },
                            )

        await conversation_service.add_message(
            conversation_id=conversation_id, role="user", content=payload.message
        )
        confidence = compute_confidence(hits, answer_text=final_text)
        assistant_message = await conversation_service.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_text or "I could not produce an answer — please retry.",
            confidence=confidence.score,
            from_vault=confidence.from_vault,
        )
        await conversation_service.add_citations(assistant_message.id, hits)
        await conversation_service.add_tool_calls(assistant_message.id, audit)
        await remember_turn(
            conversation_id=conversation_id, role="user", content=payload.message
        )
        if final_text:
            await remember_turn(
                conversation_id=conversation_id,
                role="assistant",
                content=final_text,
            )

        yield sse_event(
            "confidence",
            {
                "score": confidence.score,
                "level": confidence.level,
                "from_vault": confidence.from_vault,
                "rationale": confidence.rationale,
            },
        )
        for draft in pending:
            yield sse_event("confirm_required", draft)
        yield sse_event(
            "done",
            {
                "conversation_id": str(conversation_id),
                "message_id": str(assistant_message.id),
                "refused": not confidence.from_vault,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("chat stream failed")
        yield sse_event("error", {"detail": f"{type(exc).__name__}: {exc}"})


@router.post("/chat")
async def chat(payload: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat(payload),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
