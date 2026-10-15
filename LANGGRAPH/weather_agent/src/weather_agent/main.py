from fastapi import FastAPI
from pydantic import BaseModel, Field

from weather_agent.graph import weather_graph
from weather_agent.state import AgentState

app = FastAPI(title="Weather Places Agent", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1, description="Natural language message with a temperature"
    )


class ChatResponse(BaseModel):
    reply: str
    temperature: float | None
    exact_match: bool
    fallback_used: bool
    candidates: list[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    final_state: AgentState = weather_graph.invoke(
        {
            "message": req.message,
            "temperature": None,
            "unit": "C",
            "candidates": [],
            "exact_match": False,
            "fallback_used": False,
            "summary": "",
            "recommendations": [],
            "answer": "",
        }
    )
    return ChatResponse(
        reply=final_state.get("answer", ""),
        temperature=final_state.get("temperature"),
        exact_match=final_state.get("exact_match", False),
        fallback_used=final_state.get("fallback_used", False),
        candidates=final_state.get("candidates", []),
    )
