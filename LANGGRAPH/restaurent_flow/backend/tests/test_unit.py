from __future__ import annotations

from pizza_world.agents.graph import route_after_feedback, route_after_pay_later, route_from_router
from pizza_world.agents.router import _fallback_classify, _fallback_items
from pizza_world.agents.state import CartLine
from pizza_world.agents.tools import calculate_total, format_cart, pay_later_due_date
from pizza_world.api.v1.kitchen import NEXT_STATUS


def test_calculate_total_two_tikka_one_zinger() -> None:
    cart = [
        CartLine(item_name="Chicken Tikka", size="Medium", qty=2, unit_price=900.0).model_dump(),
        CartLine(item_name="Zinger Burger", size="Regular", qty=1, unit_price=350.0).model_dump(),
    ]
    assert calculate_total(cart) == 2150.0


def test_calculate_total_empty() -> None:
    assert calculate_total([]) == 0.0


def test_format_cart_empty() -> None:
    assert "empty" in format_cart([]).lower()


def test_pay_later_due_date_three_days() -> None:
    from datetime import UTC, datetime

    due = pay_later_due_date(3)
    delta = due - datetime.now(UTC)
    assert 2.9 < delta.total_seconds() / 86400 < 3.1


def test_fallback_items_extraction() -> None:
    items = _fallback_items("I want 2 Chicken Tikka Medium and 1 Zinger Burger")
    assert len(items) == 2
    assert items[0].name == "Chicken Tikka"
    assert items[0].size == "Medium"
    assert items[0].qty == 2
    assert items[1].name == "Zinger Burger"
    assert items[1].qty == 1


def test_fallback_classifier_intents() -> None:
    assert _fallback_classify("show me the menu").intent == "view_menu"
    assert _fallback_classify("what's my total?").intent == "show_total"
    assert _fallback_classify("pay now cash").intent == "pay_now"
    assert _fallback_classify("borrow pay later 3 days").intent == "pay_later"
    assert _fallback_classify("add 2 Chicken Tikka Medium").intent == "add_items"
    assert _fallback_classify("hello there").intent == "general"


def test_route_from_router_maps_intents() -> None:
    assert route_from_router({"intent": "view_menu"}) == "view_menu"
    assert route_from_router({"intent": "add_items"}) == "add_items"
    assert route_from_router({"intent": "show_total"}) == "show_total"
    assert route_from_router({"intent": "pay_now"}) == "pay_now"
    assert route_from_router({"intent": "pay_later"}) == "pay_later"
    assert route_from_router({"intent": "general"}) == "general"
    assert route_from_router({}) == "general"  # fallback


def test_route_after_pay_later_threshold() -> None:
    assert route_after_pay_later({"total": 7600.0}) == "human_feedback"
    assert route_after_pay_later({"total": 7000.0}) == "persist_order"  # strictly above
    assert route_after_pay_later({"total": 200.0}) == "persist_order"


def test_route_after_feedback() -> None:
    assert route_after_feedback({"human_feedback": {"approved": True}}) == "persist_order"
    assert route_after_feedback({"human_feedback": {"approved": False}}) == "reject"
    assert route_after_feedback({}) == "reject"


def test_kitchen_transition_map() -> None:
    assert NEXT_STATUS == {
        "placed": "preparing",
        "preparing": "ready",
        "ready": "on_ride",
        "on_ride": "delivered",
    }


def test_cart_line_line_total() -> None:
    line = CartLine(item_name="Deal 6", size="Regular", qty=4, unit_price=1900.0)
    assert line.line_total == 7600.0
