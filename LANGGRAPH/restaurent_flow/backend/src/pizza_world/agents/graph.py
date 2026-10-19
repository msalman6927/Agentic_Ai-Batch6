from __future__ import annotations

from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from pizza_world.agents.nodes import (
    add_items_node,
    general_node,
    human_feedback_node,
    pay_later_node,
    pay_now_node,
    persist_order_node,
    reject_node,
    router_node,
    show_total_node,
    view_menu_node,
)
from pizza_world.agents.state import ChatState
from pizza_world.config import settings

_INTENT_TO_NODE = {
    "view_menu": "view_menu",
    "add_items": "add_items",
    "show_total": "show_total",
    "pay_now": "pay_now",
    "pay_later": "pay_later",
    "general": "general",
}


def route_from_router(state: ChatState) -> str:
    return _INTENT_TO_NODE.get(state.get("intent", "general"), "general")


def route_after_pay_later(state: ChatState) -> str:
    """Human-in-the-loop gate: only borrow (pay_later) above the threshold interrupts."""
    total = state.get("total", 0.0)
    if total > settings.borrow_threshold:
        return "human_feedback"
    return "persist_order"


def route_after_feedback(state: ChatState) -> str:
    feedback = state.get("human_feedback") or {}
    if feedback.get("approved"):
        return "persist_order"
    return "reject"


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any, Any, ChatState, ChatState]:
    g: StateGraph[ChatState] = StateGraph(ChatState)

    g.add_node("router", router_node)
    g.add_node("view_menu", view_menu_node)
    g.add_node("add_items", add_items_node)
    g.add_node("show_total", show_total_node)
    g.add_node("pay_now", pay_now_node)
    g.add_node("pay_later", pay_later_node)
    g.add_node("general", general_node)
    g.add_node("human_feedback", human_feedback_node)
    g.add_node("persist_order", persist_order_node)
    g.add_node("reject", reject_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_from_router,
        list(_INTENT_TO_NODE.values()),
    )

    for name in ("view_menu", "add_items", "show_total", "general", "reject"):
        g.add_edge(name, END)

    g.add_edge("pay_now", "persist_order")

    g.add_conditional_edges(
        "pay_later",
        route_after_pay_later,
        ["human_feedback", "persist_order"],
    )
    g.add_conditional_edges(
        "human_feedback",
        route_after_feedback,
        ["persist_order", "reject"],
    )
    g.add_edge("persist_order", END)

    return g.compile(checkpointer=checkpointer)
