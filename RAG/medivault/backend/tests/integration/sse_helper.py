import json
from typing import Any


async def collect_sse(client, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """POST /chat and return the full SSE stream as [{event, data}, ...]."""
    events: list[dict[str, Any]] = []
    current_event = "message"
    async with client.stream("POST", "/chat", json=payload) as response:
        assert response.status_code == 200, await response.aread()
        async for line in response.aiter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data = json.loads(line.split(":", 1)[1].strip())
                events.append({"event": current_event, "data": data})
    return events


def event_names(events: list[dict[str, Any]]) -> list[str]:
    return [e["event"] for e in events]


def joined_tokens(events: list[dict[str, Any]]) -> str:
    return "".join(e["data"]["text"] for e in events if e["event"] == "token")
