import csv
import io
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

REQUIRED_COLUMNS = ("sale_date", "item_name", "quantity", "unit_price")


@dataclass
class SaleRow:
    sale_date: date
    item_name: str
    quantity: int
    unit_price: Decimal
    total: Decimal


@dataclass
class ParsedSales:
    rows: list[SaleRow] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw.strip())


def parse_sales_csv(content: bytes | str) -> ParsedSales:
    """Fixed schema: sale_date,item_name,quantity,unit_price (header row required)."""
    text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    result = ParsedSales()
    if reader.fieldnames is None:
        result.errors.append({"row": 0, "error": "empty CSV"})
        return result
    headers = {name.strip().lower() for name in reader.fieldnames}
    missing = [col for col in REQUIRED_COLUMNS if col not in headers]
    if missing:
        result.errors.append(
            {"row": 0, "error": f"missing required columns: {missing}"}
        )
        return result

    for line_number, raw in enumerate(reader, start=2):
        try:
            sale_date = _parse_date(raw.get("sale_date") or "")
            item_name = (raw.get("item_name") or "").strip()
            if not item_name:
                raise ValueError("item_name is blank")
            quantity = int((raw.get("quantity") or "").strip())
            if quantity <= 0:
                raise ValueError("quantity must be positive")
            unit_price = Decimal((raw.get("unit_price") or "0").strip())
            if unit_price < 0:
                raise ValueError("unit_price must be >= 0")
            total = (unit_price * quantity).quantize(Decimal("0.01"))
            result.rows.append(
                SaleRow(
                    sale_date=sale_date,
                    item_name=item_name,
                    quantity=quantity,
                    unit_price=unit_price.quantize(Decimal("0.01")),
                    total=total,
                )
            )
        except (ValueError, InvalidOperation) as exc:
            result.errors.append({"row": line_number, "error": str(exc)})
    return result
