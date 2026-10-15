import json
from typing import Any


def sse_event(name: str, payload: dict[str, Any]) -> str:
    return (
        f"event: {name}\n"
        f"data: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
    )


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
