
import os
from typing import Annotated
from typing_extensions import TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import BaseMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition


# 1. State Schema (Message History Memory ke sath)
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# 2. Real-World Business Tools
def get_order_details(order_id: str) -> str:
    """Fetch details and current status of a customer order."""

    orders_db = {
        "ORD-101": {
            "status": "Delivered",
            "item": "Wireless Headphones",
            "amount": 120.00,
        },
        "ORD-102": {
            "status": "In Transit",
            "item": "Gaming Mouse",
            "amount": 45.00,
        },
        "ORD-103": {
            "status": "Damaged on Arrival",
            "item": "Smart Watch",
            "amount": 250.00,
        },
    }

    order = orders_db.get(order_id.upper())

    if order:
        return (
            f"Order {order_id}: Item '{order['item']}', "
            f"Status: {order['status']}, "
            f"Total: ${order['amount']}"
        )

    return f"Order {order_id} not found in database."


def process_refund(order_id: str, reason: str, amount: float) -> str:
    """Process a financial monetary refund for an order. Highly sensitive action!"""

    return (
        f"SUCCESS: Refund of ${amount} for Order {order_id} "
        f"processed successfully. Reason: {reason}"
    )


def check_inventory(item_name: str) -> str:
    """Check stock availability for a product in warehouse."""

    inventory = {
        "smart watch": 5,
        "wireless headphones": 0,
        "gaming mouse": 12,
    }

    stock = inventory.get(item_name.lower(), 0)

    return (
        f"Inventory Check: Product '{item_name}' "
        f"has {stock} units available in warehouse."
    )


tools = [
    get_order_details,
    process_refund,
    check_inventory,
]


# 3. LLM Setup with Persona & Rules
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash"
)

llm_with_tools = llm.bind_tools(tools)

SYSTEM_PROMPT = SystemMessage(
    content=(
        "You are 'NexusSupport', an advanced E-Commerce AI Support Agent.\n"
        "Your goals:\n"
        "1. Help users check order statuses and warehouse inventory.\n"
        "2. If a customer reports a damaged item (e.g. ORD-103), "
        "look up order details first, and then offer/trigger a refund "
        "via the process_refund tool.\n"
        "3. Always maintain a helpful, professional tone."
    )
)


def assistant(state: AgentState):
    messages = [SYSTEM_PROMPT] + state["messages"]

    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}


# 4. Graph Architecture Construction
builder = StateGraph(AgentState)

builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))

builder.add_edge(START, "assistant")

builder.add_conditional_edges(
    "assistant",
    tools_condition,
)

builder.add_edge("tools", "assistant")


# 5. Breakpoint: Sensitive tools chalne se pehle execution pause hogi!
graph = builder.compile(
    interrupt_before=["tools"]
)
