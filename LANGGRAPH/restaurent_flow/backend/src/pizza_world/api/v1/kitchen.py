from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from pizza_world.core.security import ChefUser
from pizza_world.db.models import Order, OrderItem
from pizza_world.db.session import get_session_maker
from pizza_world.services.bus import ADMIN_TOPIC, KITCHEN_TOPIC, bus, user_topic
from pizza_world.services.messages import save_message

router = APIRouter(prefix="/api/v1/kitchen", tags=["kitchen"])

# Chef advances the order one step at a time (server-validated state machine).
NEXT_STATUS: dict[str, str] = {
    "placed": "preparing",
    "preparing": "ready",
    "ready": "on_ride",
    "on_ride": "delivered",
}

STATUS_ANNOUNCEMENTS: dict[str, str] = {
    "preparing": "Your order is being prepared in the kitchen.",
    "ready": "Your order is ready!",
    "on_ride": "Your order is on the way to you.",
    "delivered": "Your order has been delivered. Enjoy your meal!",
}

OPEN_STATUSES = ("placed", "preparing", "ready", "on_ride")


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class StatusIn(BaseModel):
    status: str = Field(pattern="^(preparing|ready|on_ride|delivered)$")


async def _open_orders() -> list[dict[str, Any]]:
    async with get_session_maker()() as session:
        orders = (
            (
                await session.execute(
                    select(Order).where(Order.status.in_(OPEN_STATUSES)).order_by(Order.created_at)
                )
            )
            .scalars()
            .all()
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
                "line_total": it.line_total,
            }
        )
    return [
        {
            "id": o.id,
            "user_id": o.user_id,
            "thread_id": o.thread_id,
            "status": o.status,
            "payment_mode": o.payment_mode,
            "total": o.total,
            "next_status": NEXT_STATUS.get(o.status),
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "items": items_by_order.get(o.id, []),
        }
        for o in orders
    ]


@router.get("/orders")
async def kitchen_orders(chef: ChefUser) -> dict[str, Any]:
    return {"orders": await _open_orders()}


@router.patch("/orders/{order_id}/status")
async def advance_status(order_id: str, body: StatusIn, chef: ChefUser) -> dict[str, Any]:
    async with get_session_maker()() as session:
        order = await session.get(Order, order_id)
        if order is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Order not found")
        allowed = NEXT_STATUS.get(order.status)
        if allowed is None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"Order is '{order.status}' and cannot advance further",
            )
        if body.status != allowed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                f"From '{order.status}' the next status must be '{allowed}'",
            )
        order.status = body.status
        await session.commit()

    announcement = STATUS_ANNOUNCEMENTS[body.status]
    await save_message(
        thread_id=order.thread_id,
        user_id=order.user_id,
        role="assistant",
        content=f"[Kitchen] {announcement}",
    )
    event = {
        "type": "order_status",
        "order_id": order.id,
        "status": body.status,
        "message": announcement,
    }
    await bus.publish_many([user_topic(order.user_id), KITCHEN_TOPIC, ADMIN_TOPIC], event)
    return {
        "order_id": order.id,
        "status": order.status,
        "next_status": NEXT_STATUS.get(order.status),
        "message": announcement,
    }


@router.get("/events")
async def kitchen_events(chef: ChefUser) -> StreamingResponse:
    orders = await _open_orders()

    async def stream() -> AsyncIterator[str]:
        yield sse("snapshot", {"orders": orders})
        q = bus.subscribe(KITCHEN_TOPIC)
        try:
            while True:
                event = await q.get()
                yield sse(event.get("type", "event"), event)
        finally:
            bus.unsubscribe(KITCHEN_TOPIC, q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
