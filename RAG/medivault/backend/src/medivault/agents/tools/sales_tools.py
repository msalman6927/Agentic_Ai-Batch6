import json
from datetime import date

from langchain_core.tools import tool

from medivault.services import sales_service


@tool
async def get_sales_summary(
    item_name: str = "",
    from_date: str = "",
    to_date: str = "",
) -> str:
    """Aggregate sales (quantity + revenue per item) from the sales ledger.

    item_name: optional substring filter, e.g. 'Panadol'.
    from_date/to_date: optional ISO dates (YYYY-MM-DD). Both optional.
    Use when the doctor asks how well a product is selling or wants
    pharmacy sales numbers to guide a recommendation.
    """
    start = date.fromisoformat(from_date) if from_date else None
    end = date.fromisoformat(to_date) if to_date else None
    summary = await sales_service.sales_summary(
        from_date=start, to_date=end, item_name=item_name or None
    )
    if summary["item_count"] == 0:
        return "No sales rows match those filters."
    return json.dumps(summary, ensure_ascii=False, default=str)
