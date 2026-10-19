from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy import select

from pizza_world.core.security import AdminUser
from pizza_world.db.models import Order, OrderItem, PendingApproval
from pizza_world.db.session import get_session_maker
from pizza_world.services.bus import ADMIN_TOPIC, KITCHEN_TOPIC, bus, user_topic
from pizza_world.services.messages import save_message
from pizza_world.services.runtime import get_graph

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class DecisionIn(BaseModel):
    thread_id: str
    approved: bool
    admin_comment: str = Field(default="", max_length=500)


async def _pending_from_state(thread_id: str, state: Any) -> dict[str, Any] | None:
    if not state or not getattr(state, "next", None):
        return None
    tasks = getattr(state, "tasks", ()) or ()
    for task in tasks:
        interrupts = getattr(task, "interrupts", ()) or ()
        if interrupts:
            return {
                "thread_id": thread_id,
                "order": getattr(interrupts[0], "value", None),
            }
    return None


def _pending_from_rows(rows: list[PendingApproval]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.payload)
        except json.JSONDecodeError:
            payload = {}
        out.append(
            {
                "thread_id": row.thread_id,
                "user_id": row.user_id,
                "order": payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out


@router.get("/pending-approvals")
async def pending_approvals(admin: AdminUser) -> dict[str, Any]:
    async with get_session_maker()() as session:
        rows = (
            (await session.execute(select(PendingApproval).order_by(PendingApproval.created_at)))
            .scalars()
            .all()
        )
    return {"pending": _pending_from_rows(list(rows))}


async def _run_resumed(
    thread_id: str, user_id: str, approved: bool, admin_comment: str, admin_id: str
) -> None:
    """Resume the interrupted graph in the background; persist + push every assistant message."""
    graph = await get_graph()
    config: dict[str, Any] = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": 30,
    }
    command: Command[Any] = Command(
        resume={
            "approved": approved,
            "admin_comment": admin_comment,
            "admin_id": admin_id,
            "decided_at": datetime.now(UTC).isoformat(),
        }
    )
    try:
        async for mode, payload in graph.astream(  # type: ignore[call-overload]
            command, config, stream_mode=["updates", "custom"]
        ):
            if mode == "custom":
                await bus.publish(user_topic(user_id), {"type": "custom", **(payload or {})})
                continue
            for node, update in (payload or {}).items():
                reply = (update or {}).get("reply")
                if reply:
                    await save_message(
                        thread_id=thread_id,
                        user_id=user_id,
                        role="assistant",
                        content=reply,
                    )
                    await bus.publish(
                        user_topic(user_id),
                        {"type": "assistant_message", "content": reply},
                    )
                if node == "persist_order" and (update or {}).get("order_id"):
                    await bus.publish_many(
                        [ADMIN_TOPIC, KITCHEN_TOPIC],
                        {
                            "type": "order_placed",
                            "order_id": update["order_id"],
                            "total": update.get("total"),
                            "user_id": user_id,
                            "thread_id": thread_id,
                        },
                    )
    except Exception as exc:  # noqa: BLE001
        await save_message(
            thread_id=thread_id,
            user_id=user_id,
            role="system",
            content=f"Order flow failed after decision: {exc}",
        )
        await bus.publish(
            user_topic(user_id),
            {"type": "error", "message": f"Order flow failed after decision: {exc}"},
        )


@router.post("/decide", status_code=status.HTTP_202_ACCEPTED)
async def decide(body: DecisionIn, admin: AdminUser, background: BackgroundTasks) -> dict[str, Any]:
    graph = await get_graph()
    async with get_session_maker()() as session:
        row = (
            await session.execute(
                select(PendingApproval).where(PendingApproval.thread_id == body.thread_id)
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "No pending approval for that thread (already decided or unknown)",
            )
        user_id = row.user_id
        await session.delete(row)
        await session.commit()

    # sanity: the graph must still be paused at the interrupt
    state = await graph.aget_state({"configurable": {"thread_id": body.thread_id}})
    entry = await _pending_from_state(body.thread_id, state)
    if entry is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Graph is no longer waiting on this thread (stale pending row cleared)",
        )

    await bus.publish(
        user_topic(user_id),
        {
            "type": "approval_decision",
            "thread_id": body.thread_id,
            "approved": body.approved,
            "admin_comment": body.admin_comment,
        },
    )
    background.add_task(
        _run_resumed,
        body.thread_id,
        user_id,
        body.approved,
        body.admin_comment,
        admin.id,
    )
    return {"status": "accepted", "thread_id": body.thread_id, "approved": body.approved}


@router.get("/orders")
async def all_orders(admin: AdminUser) -> dict[str, Any]:
    async with get_session_maker()() as session:
        orders = (
            (await session.execute(select(Order).order_by(Order.created_at.desc()))).scalars().all()
        )
        ids = [o.id for o in orders]
        items = (
            (await session.execute(select(OrderItem).where(OrderItem.order_id.in_(ids))))
            .scalars()
            .all()
            if ids
            else []
        )
    items_by_order: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        items_by_order.setdefault(it.order_id, []).append(
            {
                "item_name": it.item_name,
                "size": it.size,
                "qty": it.qty,
                "unit_price": it.unit_price,
                "line_total": it.line_total,
            }
        )
    return {
        "orders": [
            {
                "id": o.id,
                "user_id": o.user_id,
                "thread_id": o.thread_id,
                "status": o.status,
                "payment_mode": o.payment_mode,
                "total": o.total,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "admin_comment": o.admin_comment,
                "created_at": o.created_at.isoformat() if o.created_at else None,
                "items": items_by_order.get(o.id, []),
            }
            for o in orders
        ]
    }


@router.get("/events")
async def admin_events(admin: AdminUser) -> StreamingResponse:
    async with get_session_maker()() as session:
        rows = (
            (await session.execute(select(PendingApproval).order_by(PendingApproval.created_at)))
            .scalars()
            .all()
        )
        pending = _pending_from_rows(list(rows))
        orders = (
            (await session.execute(select(Order).order_by(Order.created_at.desc()).limit(50)))
            .scalars()
            .all()
        )
        snapshot_orders = [
            {
                "id": o.id,
                "user_id": o.user_id,
                "thread_id": o.thread_id,
                "status": o.status,
                "payment_mode": o.payment_mode,
                "total": o.total,
                "due_date": o.due_date.isoformat() if o.due_date else None,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]

    async def stream() -> AsyncIterator[str]:
        yield sse(
            "snapshot",
            {"pending": pending, "orders": snapshot_orders},
        )
        q = bus.subscribe(ADMIN_TOPIC)
        try:
            while True:
                event = await q.get()
                yield sse(event.get("type", "event"), event)
        finally:
            bus.unsubscribe(ADMIN_TOPIC, q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
