from __future__ import annotations

from typing import Any

from langgraph.graph.state import CompiledStateGraph

from pizza_world.agents.graph import build_graph
from pizza_world.agents.state import ChatState
from pizza_world.services.checkpointer import get_checkpointer

_graph: CompiledStateGraph[Any, Any, ChatState, ChatState] | None = None


async def get_graph() -> CompiledStateGraph[Any, Any, ChatState, ChatState]:
    global _graph
    if _graph is None:
        checkpointer = await get_checkpointer()
        _graph = build_graph(checkpointer=checkpointer)
    return _graph
