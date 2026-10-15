from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list[Any], add_messages]
    query: str
    conversation_id: str
    patient_id: str | None
    hits: list[Any]
    context_blocks: list[str]
    from_vault: bool
    patient_summary: str | None
    tool_audit: Annotated[list[dict], lambda a, b: a + b]
    pending_writes: Annotated[list[dict], lambda a, b: a + b]
