from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from pizza_world.core.security import AnyUser
from pizza_world.db.models import Order, PendingApproval
from pizza_world.db.session import get_session_maker
from pizza_world.services.bus import ADMIN_TOPIC, KITCHEN_TOPIC, bus, user_topic
from pizza_world.services.messages import get_thread_messages, save_message
from pizza_world.services.runtime import get_graph

router = APIRouter(prefix="/api/v1", tags=["chat"])


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _record_pending(thread_id: str, user_id: str, payload: dict[str, Any]) -> None:
    """Persist the interrupt so the admin panel can list it cheaply (and after restarts)."""
    async with get_session_maker()() as session:
        existing = (
            await session.execute(
                select(PendingApproval).where(PendingApproval.thread_id == thread_id)
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PendingApproval(
                    thread_id=thread_id,
                    user_id=user_id,
                    payload=json.dumps(payload, default=str),
                )
            )
            await session.commit()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


@router.post("/chat")
async def chat(body: ChatIn, user: AnyUser) -> StreamingResponse:
    thread_id = body.thread_id or str(uuid.uuid4())
    graph = await get_graph()
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 30,
    }
    run_input: dict[str, Any] = {
        "messages": [HumanMessage(content=body.message)],
        "user_id": user.id,
        "thread_id": thread_id,
    }
    await save_message(thread_id=thread_id, user_id=user.id, role="user", content=body.message)

    async def event_stream() -> AsyncIterator[str]:
        yield sse("thread", {"thread_id": thread_id})
        assistant_reply: str | None = None
        order_info: dict[str, Any] | None = None
        try:
            async for mode, payload in graph.astream(  # type: ignore[call-overload]
                run_input, config, stream_mode=["messages", "updates", "custom"]
            ):
                if mode == "messages":
                    chunk, meta = payload
                    text = getattr(chunk, "content", "")
                    if text and meta.get("langgraph_node") not in ("router",):
                        yield sse("token", {"delta": text, "node": meta.get("langgraph_node")})
                elif mode == "custom":
                    yield sse("custom", payload)
                elif mode == "updates":
                    for node, update in payload.items():
                        if node == "__interrupt__":
                            intr = update[0] if update else None
                            data = getattr(intr, "value", None) or {}
                            await _record_pending(thread_id, user.id, data)
                            await bus.publish(
                                ADMIN_TOPIC,
                                {
                                    "type": "pending_approval",
                                    "thread_id": thread_id,
                                    "user_id": user.id,
                                    "order": data,
                                },
                            )
                            yield sse("interrupt", {"payload": data})
                            yield sse("done", {"reason": "awaiting_approval"})
                            return
                        yield sse("node", {"node": node})
                        if node in (
                            "view_menu",
                            "add_items",
                            "show_total",
                            "pay_now",
                            "pay_later",
                            "general",
                            "human_feedback",
                            "persist_order",
                            "reject",
                        ):
                            assistant_reply = (update or {}).get("reply", assistant_reply)
                        if node == "persist_order":
                            order_info = {
                                "order_id": (update or {}).get("order_id"),
                                "total": (update or {}).get("total"),
                                "user_id": user.id,
                                "thread_id": thread_id,
                            }
            if assistant_reply:
                await save_message(
                    thread_id=thread_id,
                    user_id=user.id,
                    role="assistant",
                    content=assistant_reply,
                )
                await bus.publish(
                    user_topic(user.id),
                    {"type": "assistant_message", "content": assistant_reply},
                )
            if order_info and order_info.get("order_id"):
                await bus.publish_many(
                    [ADMIN_TOPIC, KITCHEN_TOPIC],
                    {"type": "order_placed", **order_info},
                )
            yield sse("done", {"thread_id": thread_id})
        except Exception as exc:  # noqa: BLE001 — surface any failure to the client
            yield sse("error", {"message": str(exc)})
            yield sse("done", {"thread_id": thread_id, "error": True})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chat/threads/{thread_id}/messages")
async def thread_messages(thread_id: str, user: AnyUser) -> dict[str, Any]:
    rows = await get_thread_messages(thread_id=thread_id, user_id=user.id)
    return {
        "thread_id": thread_id,
        "messages": [
            {
                "id": r.id,
                "role": r.role,
                "content": r.content,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/threads/{thread_id}/events")
async def thread_events(thread_id: str, user: AnyUser) -> StreamingResponse:
    """User-side live feed: snapshot (history + latest order status) then bus deltas."""
    from sqlalchemy import select

    graph = await get_graph()
    state = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    pending_interrupt: dict[str, Any] | None = None
    if state and getattr(state, "next", None):
        interrupts = state.tasks[0].interrupts if state.tasks else ()
        if interrupts:
            pending_interrupt = getattr(interrupts[0], "value", None)

    rows = await get_thread_messages(thread_id=thread_id, user_id=user.id)
    latest_order = None
    async with get_session_maker()() as session:
        order = (
            await session.execute(
                select(Order)
                .where(Order.thread_id == thread_id, Order.user_id == user.id)
                .order_by(Order.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if order is not None:
            latest_order = {
                "order_id": order.id,
                "status": order.status,
                "total": order.total,
                "payment_mode": order.payment_mode,
            }

    async def stream() -> AsyncIterator[str]:
        yield sse(
            "snapshot",
            {
                "thread_id": thread_id,
                "pending_approval": pending_interrupt,
                "order": latest_order,
                "messages": [
                    {
                        "role": r.role,
                        "content": r.content,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in rows
                ],
            },
        )
        q = bus.subscribe(user_topic(user.id))
        try:
            while True:
                event = await q.get()
                yield sse(event.get("type", "event"), event)
        finally:
            bus.unsubscribe(user_topic(user.id), q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/menu")
async def menu(user: AnyUser) -> dict[str, Any]:
    from pizza_world.agents.tools import view_menu

    async with get_session_maker()() as session:
        text = await view_menu(session)
    return {"menu": text}


@router.get("/orders")
async def my_orders(user: AnyUser) -> dict[str, Any]:
    from sqlalchemy import select

    async with get_session_maker()() as session:
        orders = (
            (
                await session.execute(
                    select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
                )
            )
            .scalars()
            .all()
        )
    return {
        "orders": [
            {
                "id": o.id,
                "status": o.status,
                "total": o.total,
                "payment_mode": o.payment_mode,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]
    }


@router.get("/threads/{thread_id}/order")
async def thread_order(thread_id: str, user: AnyUser) -> dict[str, Any]:
    from sqlalchemy import select

    async with get_session_maker()() as session:
        order = (
            await session.execute(
                select(Order)
                .where(Order.thread_id == thread_id, Order.user_id == user.id)
                .order_by(Order.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if order is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No order for this thread")
    return {
        "order_id": order.id,
        "status": order.status,
        "total": order.total,
        "payment_mode": order.payment_mode,
    }
