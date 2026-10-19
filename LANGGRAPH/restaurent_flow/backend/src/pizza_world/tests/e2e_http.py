"""HTTP E2E test against a running server: `uv run python -m pizza_world` first, then
`uv run python -m pizza_world.tests.e2e_http`.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"


def _sse_events(raw: str) -> list[tuple[str, dict[str, Any]]]:
    events: list[tuple[str, dict[str, Any]]] = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        ev = None
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event: "):
                ev = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:]
        if ev:
            try:
                events.append((ev, json.loads(data)))
            except json.JSONDecodeError:
                events.append((ev, {}))
    return events


async def chat_sse(
    client: httpx.AsyncClient, token: str, message: str, thread_id: str | None = None
) -> tuple[str, list[tuple[str, dict[str, Any]]]]:
    payload: dict[str, Any] = {"message": message}
    if thread_id:
        payload["thread_id"] = thread_id
    async with client.stream(
        "POST",
        f"{BASE}/api/v1/chat",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        tid = thread_id or str(uuid.uuid4())
        events: list[tuple[str, dict[str, Any]]] = []
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                current = line[7:].strip()
            elif line.startswith("data: "):
                data = json.loads(line[6:])
                events.append((current, data))
                if current == "thread":
                    tid = data["thread_id"]
    return tid, events


async def main() -> None:
    async with httpx.AsyncClient() as client:
        # --- register user
        email = f"u{uuid.uuid4().hex[:8]}@example.com"
        r = await client.post(
            f"{BASE}/api/v1/auth/register",
            json={"name": "E2E User", "email": email, "password": "secret12"},
        )
        assert r.status_code == 200, r.text
        user_tok = r.json()["access_token"]
        print("register user ok:", r.json()["role"])

        r = await client.post(
            f"{BASE}/api/v1/auth/login",
            json={"email": "admin@pizzaworld.com", "password": "admin123"},
        )
        assert r.status_code == 200, r.text
        admin_tok = r.json()["access_token"]
        print("admin login ok:", r.json()["role"])

        r = await client.post(
            f"{BASE}/api/v1/auth/login",
            json={"email": "chef@pizzaworld.com", "password": "chef123"},
        )
        assert r.status_code == 200, r.text
        chef_tok = r.json()["access_token"]
        print("chef login ok:", r.json()["role"])

        # role guard: user cannot access admin
        r = await client.get(
            f"{BASE}/api/v1/admin/orders",
            headers={"Authorization": f"Bearer {user_tok}"},
        )
        assert r.status_code == 403, r.text
        print("role guard ok (user -> admin = 403)")

        # --- 1. menu over chat
        tid, events = await chat_sse(client, user_tok, "show me the menu")
        kinds = [e for e, _ in events]
        assert "done" in kinds, events
        print("chat menu stream ok, thread:", tid[:8], "| token events:", kinds.count("token"))

        # --- 2. small pay_now order
        tid2, events = await chat_sse(client, user_tok, "add 2 Chicken Tikka Medium")
        assert any(e == "node" and d.get("node") == "add_items" for e, d in events), events
        tid2, events = await chat_sse(client, user_tok, "pay now", thread_id=tid2)
        assert any(e == "done" for e, _ in events)
        r = await client.get(
            f"{BASE}/api/v1/threads/{tid2}/order",
            headers={"Authorization": f"Bearer {user_tok}"},
        )
        assert r.status_code == 200, r.text
        order = r.json()
        print("pay_now order:", order["order_id"][:8], order["status"], order["total"])
        assert order["status"] == "placed"

        # --- 3. borrow > 7000 -> interrupt -> admin sees pending -> approve
        tid3, events = await chat_sse(client, user_tok, "add 4 Deal 6")
        tid3, events = await chat_sse(client, user_tok, "borrow pay later 3 days", thread_id=tid3)
        assert any(e == "interrupt" for e, _ in events), events
        intr = next(d for e, d in events if e == "interrupt")
        print("interrupt received, total:", intr["payload"]["total"])

        r = await client.get(
            f"{BASE}/api/v1/admin/pending-approvals",
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 200, r.text
        pending = [p for p in r.json()["pending"] if p["thread_id"] == tid3]
        assert pending, r.json()
        print("admin sees pending approval:", len(pending))

        r = await client.post(
            f"{BASE}/api/v1/admin/decide",
            json={"thread_id": tid3, "approved": True, "admin_comment": "approved via e2e"},
            headers={"Authorization": f"Bearer {admin_tok}"},
        )
        assert r.status_code == 202, r.text
        print("decide accepted:", r.json())

        # wait for background resume to persist the order
        order_id = None
        for _ in range(30):
            await asyncio.sleep(1)
            r = await client.get(
                f"{BASE}/api/v1/threads/{tid3}/order",
                headers={"Authorization": f"Bearer {user_tok}"},
            )
            if r.status_code == 200:
                order_id = r.json()["order_id"]
                print(
                    "resumed order:",
                    r.json()["status"],
                    r.json()["total"],
                    r.json()["payment_mode"],
                )
                break
        assert order_id, "order was not created after approval"

        r = await client.get(
            f"{BASE}/api/v1/chat/threads/{tid3}/messages",
            headers={"Authorization": f"Bearer {user_tok}"},
        )
        msgs = r.json()["messages"]
        print("thread messages:", [(m["role"], m["content"][:40]) for m in msgs[-3:]])

        # --- 4. kitchen advances the order
        r = await client.get(
            f"{BASE}/api/v1/kitchen/orders",
            headers={"Authorization": f"Bearer {chef_tok}"},
        )
        assert r.status_code == 200, r.text
        board = [o for o in r.json()["orders"] if o["id"] == order_id]
        assert board, "order not on kitchen board"
        print("kitchen board has order, next:", board[0]["next_status"])

        for expected in ("preparing", "ready", "on_ride", "delivered"):
            r = await client.patch(
                f"{BASE}/api/v1/kitchen/orders/{order_id}/status",
                json={"status": expected},
                headers={"Authorization": f"Bearer {chef_tok}"},
            )
            assert r.status_code == 200, r.text
            print("  chef set:", r.json()["status"])

        # illegal transition now
        r = await client.patch(
            f"{BASE}/api/v1/kitchen/orders/{order_id}/status",
            json={"status": "preparing"},
            headers={"Authorization": f"Bearer {chef_tok}"},
        )
        assert r.status_code == 409, r.text
        print("illegal transition rejected (409)")

        r = await client.get(
            f"{BASE}/api/v1/chat/threads/{tid3}/messages",
            headers={"Authorization": f"Bearer {user_tok}"},
        )
        kitchen_msgs = [m for m in r.json()["messages"] if m["content"].startswith("[Kitchen]")]
        print("kitchen announcements to user:", len(kitchen_msgs))
        assert len(kitchen_msgs) == 4

        print("\nALL HTTP E2E TESTS PASSED")


if __name__ == "__main__":
    from pizza_world.core.runner import run

    run(main())
