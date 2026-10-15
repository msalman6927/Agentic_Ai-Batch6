import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from weather_agent.config import settings
from weather_agent.state import (
    AgentState,
    BestPlacesOutcome,
    ExtractedTemperature,
    SearchOutcome,
)
from weather_agent.tools import build_search_tool

MAX_TOOL_ITERATIONS = 4


def build_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.model_name, api_key=settings.openai_api_key, temperature=0
    )


def run_websearch_agent[SchemaT: BaseModel](
    system_prompt: str, user_prompt: str, schema: type[SchemaT]
) -> SchemaT:
    llm = build_llm()
    tool = build_search_tool()
    agent_llm = llm.bind_tools([tool])
    messages = [SystemMessage(system_prompt), HumanMessage(user_prompt)]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = agent_llm.invoke(messages)
        messages.append(response)
        if not response.tool_calls:
            break
        for call in response.tool_calls:
            result = tool.invoke(call["args"])
            messages.append(
                ToolMessage(
                    json.dumps(result, ensure_ascii=False), tool_call_id=call["id"]
                )
            )

    return llm.with_structured_output(schema).invoke(messages)


def extract_temperature(state: AgentState) -> dict:
    llm = build_llm()
    result = llm.with_structured_output(ExtractedTemperature).invoke(
        [
            SystemMessage(
                "Extract the temperature the user wants from their message. "
                "If they mention Fahrenheit, keep unit 'F'. "
                "If no temperature is mentioned, return temperature=null."
            ),
            HumanMessage(state["message"]),
        ]
    )
    temperature = result.temperature
    if temperature is not None and result.unit == "F":
        temperature = round((temperature - 32) * 5 / 9, 1)

    answer = state.get("answer", "")
    if temperature is None:
        answer = "Please tell me a temperature (e.g. '25 degrees' or '78 F') and I will find places for you."
    return {"temperature": temperature, "unit": result.unit, "answer": answer}


def search_exact(state: AgentState) -> dict:
    temp = state["temperature"]
    outcome = run_websearch_agent(
        system_prompt=(
            "You are a weather research agent with a web search tool. "
            "Find countries/cities whose CURRENT temperature is exactly the target "
            f"{temp}°C (rounding to whole degrees counts as exact). "
            "Search the web, then report only places you could verify. "
            "If you cannot verify any place at exactly that temperature, return an empty list."
        ),
        user_prompt=f"Target temperature: {temp}°C. Which countries/cities currently have it?",
        schema=SearchOutcome,
    )
    matches = [m.model_dump() for m in outcome.matches]
    return {"candidates": matches, "exact_match": bool(matches)}


def search_closest(state: AgentState) -> dict:
    temp = state["temperature"]
    outcome = run_websearch_agent(
        system_prompt=(
            "You are a weather research agent with a web search tool. "
            "No place matched the target temperature exactly. Find countries/cities whose "
            f"CURRENT temperature is CLOSEST to {temp}°C, within a 3°C difference "
            f"({round(temp - 3, 1)}°C to {round(temp + 3, 1)}°C). "
            "Only report places you can verify via search; otherwise return an empty list."
        ),
        user_prompt=f"Target temperature: {temp}°C. Which nearby places are close to it?",
        schema=SearchOutcome,
    )
    matches = [m.model_dump() for m in outcome.matches]
    return {"candidates": matches, "exact_match": False, "fallback_used": True}


def best_places(state: AgentState) -> dict:
    temp = state["temperature"]
    lines = [
        f"- {c.get('city') or c['country']} ({c['country']}): {c['temperature_c']}°C"
        for c in state["candidates"]
    ]
    outcome = run_websearch_agent(
        system_prompt=(
            "You are a travel planner with a web search tool. Given candidate countries/cities "
            f"at about {temp}°C, search the web and pick the best 3-5 places to visit there "
            "for someone who wants that temperature (climate, season, attractions). "
            "Explain in one short sentence why each place fits."
        ),
        user_prompt=("Candidates:\n" + "\n".join(lines))
        + f"\nTarget temperature: {temp}°C",
        schema=BestPlacesOutcome,
    )
    recommendations = [r.model_dump() for r in outcome.recommendations]
    return {"summary": outcome.summary, "recommendations": recommendations}


def format_answer(state: AgentState) -> dict:
    temp = state["temperature"]
    recommendations = state.get("recommendations", [])
    summary = state.get("summary", "")

    header = f"Places with around {temp}°C"
    if state.get("fallback_used"):
        header += " (closest match - no exact hit found)"
    parts = [header, "", summary.strip(), "", "Best places:"]
    for rec in recommendations:
        parts.append(f"- {rec['place']} ({rec['country']}): {rec['why']}")
    return {"answer": "\n".join(parts).strip()}


def direct_reply(state: AgentState) -> dict:
    if not state.get("answer"):
        return {
            "answer": (
                f"I could not find any verified places near {state.get('temperature')}°C. "
                "Try a different temperature."
            )
        }
    return {}
