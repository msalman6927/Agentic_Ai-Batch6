from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import interrupt
from sqlalchemy.ext.asyncio import AsyncSession

from pizza_world.agents.router import classify
from pizza_world.agents.state import ChatState, HumanFeedback
from pizza_world.agents.tools import (
    add_items,
    calculate_total,
    format_cart,
    pay_later_due_date,
    view_menu,
)
from pizza_world.config import settings
from pizza_world.db.models import Order, OrderItem, Payment
from pizza_world.db.session import get_session_maker


async def _session() -> AsyncSession:
    return get_session_maker()()


def _user_text(state: ChatState) -> str:
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return ""


async def router_node(state: ChatState) -> dict[str, Any]:
    decision = await classify(_user_text(state))
    return {"intent": decision.intent, "messages": []}


async def view_menu_node(state: ChatState) -> dict[str, Any]:
    async with await _session() as session:
        text = await view_menu(session)
    reply = f"Here's our full menu:\n\n{text}"
    return {
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def add_items_node(state: ChatState) -> dict[str, Any]:
    async with await _session() as session:
        decision = await classify(_user_text(state))
        cart, resolved, problems = await add_items(session, state.get("cart", []), decision.items)
    total = calculate_total(cart)
    parts: list[str] = []
    if resolved:
        parts.append("Added to your cart:\n  " + "\n  ".join(resolved))
    if problems:
        parts.append("Problems:\n  " + "\n  ".join(problems))
    parts.append(format_cart(cart))
    parts.append("Tell me the total, or say 'pay now' / 'pay later' when you're ready.")
    reply = "\n".join(parts)
    return {
        "cart": cart,
        "total": total,
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def show_total_node(state: ChatState) -> dict[str, Any]:
    cart = state.get("cart", [])
    if not cart:
        reply = "Your cart is empty. What would you like to order?"
    else:
        reply = f"{format_cart(cart)}\nYou can pay now, or pay later (up to 3 days)."
    return {"total": calculate_total(cart), "reply": reply, "messages": [AIMessage(content=reply)]}


async def pay_now_node(state: ChatState) -> dict[str, Any]:
    total = calculate_total(state.get("cart", []))
    if total <= 0:
        reply = "Your cart is empty — add something before paying."
        return {"reply": reply, "messages": [AIMessage(content=reply)]}
    reply = f"Great — you'll pay Rs.{total:g} now (cash on delivery). Confirming your order..."
    return {
        "payment_mode": "now",
        "total": total,
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def pay_later_node(state: ChatState) -> dict[str, Any]:
    total = calculate_total(state.get("cart", []))
    if total <= 0:
        reply = "Your cart is empty — add something before setting up pay-later."
        return {"reply": reply, "messages": [AIMessage(content=reply)]}
    due = pay_later_due_date(settings.pay_later_days).isoformat()
    reply = (
        f"Pay-later requested: Rs.{total:g}, due within {settings.pay_later_days} days "
        f"(by {due[:10]})."
    )
    return {
        "payment_mode": "later",
        "total": total,
        "due_date": due,
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def general_node(state: ChatState) -> dict[str, Any]:
    text = _user_text(state).lower()
    if any(w in text for w in ("hello", "hi", "salam", "assalam", "hey")):
        reply = (
            "Assalam-o-Alaikum! Welcome to Pizza World. "
            "Ask for the menu, place an order, or ask about deals."
        )
    elif any(w in text for w in ("thank", "shukriya", "jazak")):
        reply = "You're welcome! Enjoy your meal."
    elif "deal" in text:
        reply = (
            "We have 6 opening deals (Rs.650–Rs.2400) — ask for the menu to see them all, "
            "or say e.g. 'add Deal 2'."
        )
    else:
        reply = (
            "I can help with the menu, taking your order, totals, and payment "
            "(now or within 3 days). What would you like?"
        )
    return {"reply": reply, "messages": [AIMessage(content=reply)]}


async def human_feedback_node(state: ChatState) -> dict[str, Any]:
    """Pause for admin approval on pay_later orders above the threshold.

    The resume payload (Command(resume=...)) is written into state["human_feedback"].
    """
    total = state.get("total", 0.0)
    payload = {
        "type": "borrow_approval_required",
        "thread_id": state.get("thread_id", ""),
        "user_id": state.get("user_id", ""),
        "items": state.get("cart", []),
        "total": total,
        "threshold": settings.borrow_threshold,
    }
    resume: dict[str, Any] = interrupt(payload) or {}
    feedback = HumanFeedback(
        approved=bool(resume.get("approved", False)),
        admin_comment=str(resume.get("admin_comment", "")),
        admin_id=str(resume.get("admin_id", "")),
        decided_at=str(resume.get("decided_at", datetime.now(UTC).isoformat())),
    )
    if feedback.approved:
        reply = f"Admin approved your pay-later order of Rs.{total:g}. Placing it now..."
    else:
        reply = (
            "Unfortunately the admin declined the pay-later request"
            + (f" ({feedback.admin_comment})." if feedback.admin_comment else ".")
            + " You can try 'pay now' instead."
        )
    return {
        "human_feedback": feedback.model_dump(),
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def reject_node(state: ChatState) -> dict[str, Any]:
    feedback = state.get("human_feedback") or {}
    reply = (
        "Your pay-later order was not placed"
        + (f": {feedback.get('admin_comment')}" if feedback.get("admin_comment") else ".")
        + " You can order again with 'pay now'."
    )
    return {"reply": reply, "messages": [AIMessage(content=reply)]}


async def persist_order_node(state: ChatState) -> dict[str, Any]:
    """Write order + items + payment rows; status flows onward to 'placed' on success."""
    cart = state.get("cart", [])
    total = calculate_total(cart)
    if total <= 0:
        reply = "Nothing to order — your cart is empty."
        return {"reply": reply, "messages": [AIMessage(content=reply)]}

    mode = state.get("payment_mode") or "now"
    feedback = state.get("human_feedback") or {}
    due_date = pay_later_due_date(settings.pay_later_days) if mode == "later" else None

    async with await _session() as session:
        order = Order(
            user_id=state["user_id"],
            thread_id=state["thread_id"],
            status="confirmed",
            payment_mode=mode,
            total=total,
            due_date=due_date,
            admin_comment=feedback.get("admin_comment"),
        )
        session.add(order)
        await session.flush()
        session.add_all(
            OrderItem(
                order_id=order.id,
                item_name=line["item_name"],
                size=line.get("size"),
                qty=line["qty"],
                unit_price=line["unit_price"],
                line_total=round(line["qty"] * line["unit_price"], 2),
            )
            for line in cart
        )
        session.add(
            Payment(
                order_id=order.id,
                amount=total,
                method=mode,
                status="paid" if mode == "now" else "due",
                paid_at=datetime.now(UTC) if mode == "now" else None,
                due_date=due_date,
            )
        )
        order.status = "placed"
        await session.commit()
        order_id = order.id

    paid_part = (
        f"Paid Rs.{total:g} — " if mode == "now" else f"Pay-later (due {str(due_date)[:10]}) — "
    )
    reply = (
        f"Order confirmed! Order #{order_id[:8]}. {paid_part}Rs.{total:g} total. "
        "The kitchen will update you live: preparing → ready → on ride → delivered."
    )
    return {
        "order_id": order_id,
        "total": total,
        "reply": reply,
        "messages": [AIMessage(content=reply)],
    }


async def empty_cart_after_order(state: ChatState) -> dict[str, Any]:
    return {"cart": []}
