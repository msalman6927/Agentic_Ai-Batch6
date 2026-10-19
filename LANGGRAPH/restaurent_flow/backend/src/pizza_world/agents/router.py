from __future__ import annotations

import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from pizza_world.agents.state import ExtractedItem, RouterDecision
from pizza_world.config import settings

log = logging.getLogger(__name__)

_SYSTEM = """You are the intent router for Pizza World's ordering chatbot.
Classify the latest user message into exactly ONE intent:
- view_menu: user wants to see/browse the menu or asks what food is available
- add_items: user wants to order one or more items (extract name, optional size, qty)
- show_total: user asks for the cart total / bill / how much
- pay_now: user wants to pay immediately / pay on delivery now / cash immediately
- pay_later: user wants to pay after some days / borrow / credit / "pay later" / delayed payment
- general: smalltalk, greetings, thanks, questions unrelated to the above

For add_items, extract EVERY item mentioned with quantity and size when given.
Sizes on the menu are like: Small, Medium, Large, Half, Full, 5 pcs, 10 pcs, 20 pcs.
If no size is given, leave size null.

Respond with ONLY a JSON object, no markdown fences:
{"intent": "...", "items": [{"name": "...", "size": null, "qty": 1}], "reason": "short why"}"""

_SIZES = ("Small", "Medium", "Large", "Half", "Full")


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )


def _parse(content: str) -> RouterDecision:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    data = json.loads(text)
    return RouterDecision.model_validate(data)


def _fallback_items(text: str) -> list[ExtractedItem]:
    """Extract 'qty Name (Size)' phrases without the LLM."""
    items: list[ExtractedItem] = []
    pattern = re.compile(
        r"(\d+)\s+(?:x\s+)?([A-Za-z][A-Za-z0-9&'\s]+?)"
        r"(?=\s+\d+\s|\s+and\s+|\s*,\s*|$)"
    )
    for m in pattern.finditer(text):
        qty = int(m.group(1))
        name = m.group(2).strip()
        size = None
        for sz in _SIZES:
            if name.lower().endswith(sz.lower()) and len(name) > len(sz):
                size = sz
                name = name[: -len(sz)].strip()
                break
        items.append(ExtractedItem(name=name, size=size, qty=max(1, qty)))
    return items


def _fallback_classify(text: str) -> RouterDecision:
    """Keyword router used when the LLM is unreachable (e.g. invalid API key)."""
    t = text.lower()
    pay_later_re = (
        r"\b(pay later|borrow|credit|after \d+ days|in \d+ days|"
        r"later payment|delayed payment|pay after)\b"
    )
    if re.search(pay_later_re, t):
        return RouterDecision(intent="pay_later", reason="fallback: pay-later keywords")
    if re.search(r"\b(pay now|cash|immediately|right now|pay at once|instant)\b", t):
        return RouterDecision(intent="pay_now", reason="fallback: pay-now keywords")
    if re.search(r"\b(total|bill|how much|cost of|grand total)\b", t):
        return RouterDecision(intent="show_total", reason="fallback: total keywords")
    items = _fallback_items(text)
    if items and re.search(r"\b(add|want|order|give|i'd like|like to|take)\b", t):
        return RouterDecision(intent="add_items", items=items, reason="fallback: order keywords")
    if re.search(r"\b(menu|deals?|what do you have|what's available|food|pizza)\b", t):
        return RouterDecision(intent="view_menu", reason="fallback: menu keywords")
    if items:
        return RouterDecision(intent="add_items", items=items, reason="fallback: qty+name found")
    return RouterDecision(intent="general", reason="fallback: no rule matched")


_llm_disabled = False  # circuit breaker: set after the first auth/network failure


async def classify(text: str) -> RouterDecision:
    global _llm_disabled
    if not _llm_disabled:
        prompt = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=text),
        ]
        for _ in range(2):
            try:
                raw = await _llm().ainvoke(prompt)
                return _parse(str(raw.content))
            except Exception as exc:  # noqa: BLE001 — degrade to keywords on any LLM failure
                log.warning("LLM classify failed (%s); using keyword fallback", exc)
                _llm_disabled = True
                break
    return _fallback_classify(text)
