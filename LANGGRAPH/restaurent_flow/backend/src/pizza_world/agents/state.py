from __future__ import annotations

from typing import Annotated, Any, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class CartLine(BaseModel):
    item_name: str
    size: str | None = None
    qty: int = Field(ge=1)
    unit_price: float = Field(ge=0)

    @property
    def line_total(self) -> float:
        return round(self.unit_price * self.qty, 2)


class ExtractedItem(BaseModel):
    """What the LLM extracts from the user message (names only — prices come from SQL)."""

    name: str
    size: str | None = None
    qty: int = Field(default=1, ge=1)


class RouterDecision(BaseModel):
    intent: Literal[
        "view_menu",
        "add_items",
        "show_total",
        "pay_now",
        "pay_later",
        "general",
    ]
    items: list[ExtractedItem] = Field(default_factory=list)
    reason: str = ""


class HumanFeedback(BaseModel):
    approved: bool
    admin_comment: str = ""
    admin_id: str = ""
    decided_at: str = ""


class ChatState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    thread_id: str
    cart: NotRequired[list[dict[str, Any]]]
    total: NotRequired[float]
    payment_mode: NotRequired[Literal["now", "later"] | None]
    due_date: NotRequired[str | None]
    order_id: NotRequired[str | None]
    human_feedback: NotRequired[dict[str, Any] | None]
    intent: NotRequired[str]
    reply: NotRequired[str]
