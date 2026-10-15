from langgraph.graph import END, START, StateGraph

from weather_agent.nodes import (
    best_places,
    direct_reply,
    extract_temperature,
    format_answer,
    search_closest,
    search_exact,
)
from weather_agent.state import AgentState


def route_after_extract(state: AgentState) -> str:
    return "search_exact" if state.get("temperature") is not None else "direct_reply"


def route_after_exact(state: AgentState) -> str:
    return "best_places" if state.get("candidates") else "search_closest"


def route_after_closest(state: AgentState) -> str:
    return "best_places" if state.get("candidates") else "direct_reply"


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("extract_temperature", extract_temperature)
    graph.add_node("search_exact", search_exact)
    graph.add_node("search_closest", search_closest)
    graph.add_node("best_places", best_places)
    graph.add_node("format_answer", format_answer)
    graph.add_node("direct_reply", direct_reply)

    graph.add_edge(START, "extract_temperature")
    graph.add_conditional_edges(
        "extract_temperature",
        route_after_extract,
        {"search_exact": "search_exact", "direct_reply": "direct_reply"},
    )
    graph.add_conditional_edges(
        "search_exact",
        route_after_exact,
        {"best_places": "best_places", "search_closest": "search_closest"},
    )
    graph.add_conditional_edges(
        "search_closest",
        route_after_closest,
        {"best_places": "best_places", "direct_reply": "direct_reply"},
    )
    graph.add_edge("best_places", "format_answer")
    graph.add_edge("format_answer", END)
    graph.add_edge("direct_reply", END)
    return graph.compile()


weather_graph = build_graph()
