"""Scripted E2E graph test (no HTTP).

Run: uv run python -m pizza_world.tests.e2e_graph
"""

from __future__ import annotations

import uuid
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from sqlalchemy import select

from pizza_world.core.runner import run
from pizza_world.db.models import Order, User
from pizza_world.db.session import dispose_engine, get_session_maker
from pizza_world.services.checkpointer import aclose_checkpointer, get_checkpointer
from pizza_world.services.runtime import get_graph


def _cfg(thread_id: str) -> RunnableConfig:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 30}


async def _user_id() -> str:
    async with get_session_maker()() as s:
        u = (await s.execute(select(User).where(User.role == "user").limit(1))).scalar_one_or_none()
        if u is None:
            from pizza_world.core.security import hash_password

            u = User(
                name="Tester",
                email="tester@example.com",
                password_hash=hash_password("test123"),
                role="user",
            )
            s.add(u)
            await s.commit()
            await s.refresh(u)
        return u.id


async def _replies(graph: Any, thread_id: str, user_id: str, text: str) -> list[str]:
    out: list[str] = []
    async for mode, payload in graph.astream(
        {
            "messages": [HumanMessage(content=text)],
            "user_id": user_id,
            "thread_id": thread_id,
        },
        _cfg(thread_id),
        stream_mode=["updates"],
    ):
        if mode != "updates":
            continue
        for node, update in payload.items():
            if node == "__interrupt__":
                out.append(f"INTERRUPT:{update[0].value}")
            elif isinstance(update, dict) and update.get("reply"):
                out.append(f"{node}: {update['reply']}")
    return out


async def main() -> None:
    await get_checkpointer()
    graph = await get_graph()
    user_id = await _user_id()

    # --- 1. menu question
    t1 = str(uuid.uuid4())
    print("=== 1. view menu ===")
    for r in await _replies(graph, t1, user_id, "what's on the menu?"):
        print(" ", r[:120], "..." if len(r) > 120 else "")

    # --- 2. add items + total
    t2 = str(uuid.uuid4())
    print("\n=== 2. order + total ===")
    for r in await _replies(
        graph, t2, user_id, "I want 2 Chicken Tikka Medium and 1 Zinger Burger"
    ):
        print(" ", r[:200])
    for r in await _replies(graph, t2, user_id, "what's my total?"):
        print(" ", r[:200])

    # --- 3. pay now
    t3 = str(uuid.uuid4())
    print("\n=== 3. pay now (small order) ===")
    await _replies(graph, t3, user_id, "add 1 Chicken Shawarma")
    for r in await _replies(graph, t3, user_id, "pay now"):
        print(" ", r[:200])
    async with get_session_maker()() as s:
        o = (await s.execute(select(Order).where(Order.thread_id == t3))).scalar_one_or_none()
        print(
            "  order in DB:",
            o.id[:8] if o else None,
            o.status if o else None,
            o.payment_mode if o else None,
            o.total if o else None,
        )
        assert o is not None and o.status == "placed" and o.payment_mode == "now"

    # --- 4. borrow > 7000 -> interrupt -> resume approved
    t4 = str(uuid.uuid4())
    print("\n=== 4. borrow 7600 (HITL interrupt -> approve) ===")
    await _replies(graph, t4, user_id, "add 4 Deal 6")  # 4 x 1900 = 7600 > 7000
    out = await _replies(graph, t4, user_id, "I want to pay later after 3 days")
    print(" ", out)
    assert any(x.startswith("INTERRUPT") for x in out), "expected interrupt"

    state = await graph.aget_state(_cfg(t4))
    print("  state.next:", state.next, "| total:", state.values.get("total"))

    print("  resuming with approved=True ...")
    async for mode, payload in graph.astream(
        Command(resume={"approved": True, "admin_comment": "ok", "admin_id": "admin-1"}),
        _cfg(t4),
        stream_mode=["updates"],
    ):
        if mode == "updates" and isinstance(payload, dict):
            for node, update in payload.items():
                if isinstance(update, dict) and update.get("reply"):
                    print(f"  {node}: {update['reply'][:200]}")
    async with get_session_maker()() as s:
        o = (await s.execute(select(Order).where(Order.thread_id == t4))).scalar_one_or_none()
        print(
            "  order:",
            o.id[:8] if o else None,
            o.status if o else None,
            o.payment_mode if o else None,
            o.total if o else None,
            "due:",
            o.due_date if o else None,
        )
        assert o is not None and o.status == "placed" and o.payment_mode == "later"
        assert o.due_date is not None

    # --- 5. borrow rejected path
    t5 = str(uuid.uuid4())
    print("\n=== 5. borrow rejected ===")
    await _replies(graph, t5, user_id, "add 4 Deal 6")
    out = await _replies(graph, t5, user_id, "borrow pay later")
    assert any(x.startswith("INTERRUPT") for x in out)
    async for mode, payload in graph.astream(
        Command(resume={"approved": False, "admin_comment": "credit limit"}),
        _cfg(t5),
        stream_mode=["updates"],
    ):
        if mode == "updates" and isinstance(payload, dict):
            for node, update in payload.items():
                if isinstance(update, dict) and update.get("reply"):
                    print(f"  {node}: {update['reply'][:200]}")
    async with get_session_maker()() as s:
        o = (await s.execute(select(Order).where(Order.thread_id == t5))).scalar_one_or_none()
        print("  order created?", o)
        assert o is None

    print("\nALL GRAPH TESTS PASSED")

    await aclose_checkpointer()
    await dispose_engine()


if __name__ == "__main__":
    run(main())
