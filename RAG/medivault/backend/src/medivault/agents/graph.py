import contextlib
import json
import logging
from uuid import UUID

from langchain_core.messages import (
    AIMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph

from medivault.agents.prompts import assemble_system_prompt
from medivault.agents.state import AgentState
from medivault.agents.tools.registry import TOOL_MAP, TOOLS
from medivault.config import get_settings
from medivault.llm.chat import get_chat_model
from medivault.retrieval.graph import expand_patient_graph
from medivault.retrieval.hybrid import RetrievalHit, hybrid_search

logger = logging.getLogger(__name__)


def _as_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content) if content else ""


async def retrieve_node(state: AgentState) -> dict:
    hits: list[RetrievalHit] = await hybrid_search(
        state["query"], k=get_settings().retrieval_top_k
    )
    context_blocks = [
        f"[{index}] ({hit.doc_type or 'chunk'}) {hit.snippet}"
        for index, hit in enumerate(hits, start=1)
    ]
    patient_summary = None
    if state.get("patient_id"):
        try:
            parsed = UUID(state["patient_id"])
            graph_context = await expand_patient_graph(parsed)
            patient_summary = graph_context.patient_name
            context_blocks.append(
                f"[patient-graph] {graph_context.patient_name}: "
                f"conditions={graph_context.conditions}, "
                f"candidates="
                f"{[c['generic_name'] for c in graph_context.candidate_medicines]}, "
                f"interactions={len(graph_context.interactions)}, "
                f"allergy_flags={graph_context.allergy_flags}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("patient graph inject failed: %s", exc)
    return {
        "hits": hits,
        "context_blocks": context_blocks,
        "from_vault": bool(hits),
        "patient_summary": patient_summary,
    }


async def agent_node(state: AgentState) -> dict:
    settings = get_settings()
    system = assemble_system_prompt(
        context_blocks=state.get("context_blocks", []),
        patient_summary=state.get("patient_summary"),
    )
    model = get_chat_model().bind_tools(TOOLS)
    messages = [SystemMessage(content=system), *state["messages"]]
    response = await model.ainvoke(
        messages,
        config={
            "tags": ["medivault-agent"],
            "metadata": {"max_output_tokens": settings.chat_max_output_tokens},
        },
    )
    return {"messages": [response]}


async def tools_node(state: AgentState) -> dict:
    last = state["messages"][-1]
    results: list[ToolMessage] = []
    audit: list[dict] = []
    pending: list[dict] = []

    for call in getattr(last, "tool_calls", []) or []:
        name = call.get("name", "")
        args = call.get("args", {}) or {}
        tool = TOOL_MAP.get(name)
        if tool is None:
            content = f"Unknown tool: {name}"
            status = "error"
        else:
            try:
                content = await tool.ainvoke(args)
                content = _as_text(content)
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                logger.exception("tool %s failed", name)
                content = f"Tool error: {type(exc).__name__}: {exc}"
                status = "error"
        audit.append(
            {
                "tool": name,
                "args": args,
                "summary": content[:500],
                "status": status,
            }
        )
        if name == "record_consultation" and content.startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                pending.append(json.loads(content))
        results.append(ToolMessage(content=content, tool_call_id=call.get("id", "")))
    return {"messages": results, "tool_audit": audit, "pending_writes": pending}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        steps = sum(
            1
            for message in state["messages"]
            if isinstance(message, AIMessage) and message.tool_calls
        )
        if steps < get_settings().max_agent_steps:
            return "tools"
    return END


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tools_node)
    workflow.add_edge(START, "retrieve")
    workflow.add_edge("retrieve", "agent")
    workflow.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")
    return workflow.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
