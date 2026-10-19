"""Deterministic menu/order tools. The LLM never sets a price — every figure comes from SQL."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from difflib import get_close_matches
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pizza_world.agents.state import CartLine, ExtractedItem
from pizza_world.db.models import MenuItem

DEFAULT_SIZE = "Regular"


async def view_menu(session: AsyncSession, category: str | None = None) -> str:
    stmt = select(MenuItem).order_by(MenuItem.category, MenuItem.name, MenuItem.size)
    if category:
        stmt = stmt.where(MenuItem.category == category)
    rows = (await session.execute(stmt)).scalars().all()
    if not rows:
        return "The menu is empty right now."

    lines: list[str] = ["PIZZA WORLD MENU (all prices in Rs.)", ""]
    current = None
    for item in rows:
        if item.category != current:
            current = item.category
            lines.append(f"== {current.replace('_', ' ').title()} ==")
        size = f" ({item.size})" if item.size else ""
        lines.append(f"- {item.name}{size}: {item.price:g}")
    lines.append("")
    lines.append("Timing: 3 PM to 2 AM | Free Home Delivery | 10% off 4-5-6 June 2026")
    return "\n".join(lines)


async def _lookup_item(session: AsyncSession, name: str, size: str | None) -> MenuItem | None:
    """Exact-ish lookup: normalize name, prefer requested size, fall back to single-size item."""
    norm = name.strip().lower()
    rows = (await session.execute(select(MenuItem))).scalars().all()

    def norm_name(v: str) -> str:
        return " ".join(v.lower().replace("-", " ").split())

    candidates = [r for r in rows if norm_name(r.name) == norm]
    if not candidates:
        close = get_close_matches(norm, [norm_name(r.name) for r in rows], n=1, cutoff=0.65)
        if close:
            candidates = [r for r in rows if norm_name(r.name) == close[0]]
    if not candidates:
        return None

    if size:
        want = size.strip().lower()
        for r in candidates:
            if r.size and r.size.strip().lower() == want:
                return r
    if len(candidates) == 1:
        return candidates[0]
    single = [r for r in candidates if r.size is None]
    if len(single) == 1:
        return single[0]
    return None


async def add_items(
    session: AsyncSession, cart: list[dict[str, Any]], extracted: list[ExtractedItem]
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Resolve extracted items against menu_items; merge quantities into the cart.

    Returns (new_cart, resolved_descriptions, problems).
    """
    new_cart = [CartLine.model_validate(line).model_dump() for line in cart]
    resolved: list[str] = []
    problems: list[str] = []

    for item in extracted:
        match = await _lookup_item(session, item.name, item.size)
        if match is None:
            if item.size:
                problems.append(
                    f"'{item.name}' ({item.size}) is not on the menu — please check the menu "
                    "and try again."
                )
            else:
                avail = (
                    (
                        await session.execute(
                            select(MenuItem).where(MenuItem.name.ilike(f"%{item.name.strip()}%"))
                        )
                    )
                    .scalars()
                    .all()
                )
                if avail:
                    opts = ", ".join(
                        f"{a.name} ({a.size or 'one size'} Rs.{a.price:g})" for a in avail[:6]
                    )
                    problems.append(f"'{item.name}' needs a size. Available: {opts}.")
                else:
                    problems.append(f"'{item.name}' is not on the menu.")
            continue

        size = match.size or DEFAULT_SIZE
        existing = next(
            (
                line
                for line in new_cart
                if line["item_name"].lower() == match.name.lower()
                and (line["size"] or "").lower() == size.lower()
            ),
            None,
        )
        if existing:
            existing["qty"] += item.qty
        else:
            new_cart.append(
                CartLine(
                    item_name=match.name,
                    size=size,
                    qty=item.qty,
                    unit_price=match.price,
                ).model_dump()
            )
        resolved.append(f"{item.qty} x {match.name} ({size}) @ Rs.{match.price:g}")

    return new_cart, resolved, problems


def calculate_total(cart: list[dict[str, Any]]) -> float:
    total = sum(float(line["qty"]) * float(line["unit_price"]) for line in cart)
    return round(total, 2)


def format_cart(cart: list[dict[str, Any]]) -> str:
    if not cart:
        return "Your cart is empty."
    lines = ["Your cart:"]
    for line in cart:
        size = line.get("size") or "-"
        total = line["qty"] * line["unit_price"]
        lines.append(
            f"  {line['qty']} x {line['item_name']} ({size}) "
            f"@ Rs.{line['unit_price']:g} = Rs.{total:g}"
        )
    lines.append(f"Total: Rs.{calculate_total(cart):g}")
    return "\n".join(lines)


def pay_later_due_date(days: int = 3) -> datetime:
    return datetime.now(UTC) + timedelta(days=days)
