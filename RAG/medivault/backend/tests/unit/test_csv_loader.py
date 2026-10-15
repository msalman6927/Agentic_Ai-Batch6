from datetime import date
from decimal import Decimal

from medivault.ingestion.csv_loader import parse_sales_csv


def test_parse_valid_csv() -> None:
    content = (
        "sale_date,item_name,quantity,unit_price\n"
        "2026-01-05,Panadol,10,5.50\n"
        "2026-01-06,Brufen,4,12.00\n"
    )
    result = parse_sales_csv(content)
    assert result.errors == []
    assert len(result.rows) == 2
    first = result.rows[0]
    assert first.sale_date == date(2026, 1, 5)
    assert first.quantity == 10
    assert first.total == Decimal("55.00")


def test_parse_csv_with_bad_rows() -> None:
    content = (
        "sale_date,item_name,quantity,unit_price\n"
        "2026-01-05,Panadol,10,5.50\n"
        "not-a-date,Panadol,10,5.50\n"
        "2026-01-06,,4,12.00\n"
        "2026-01-07,Brufen,-1,12.00\n"
    )
    result = parse_sales_csv(content)
    assert len(result.rows) == 1
    assert len(result.errors) == 3
    assert result.errors[0]["row"] == 3


def test_parse_csv_missing_columns() -> None:
    result = parse_sales_csv("item_name,quantity\nPanadol,5\n")
    assert result.rows == []
    assert "missing required columns" in result.errors[0]["error"]


def test_parse_empty_csv() -> None:
    result = parse_sales_csv("")
    assert result.rows == []
    assert result.errors == [{"row": 0, "error": "empty CSV"}]


def test_parse_csv_bom() -> None:
    content = (
        "﻿sale_date,item_name,quantity,unit_price\n2026-02-01,Panadol,2,5.00\n"
    ).encode()
    result = parse_sales_csv(content)
    assert result.errors == []
    assert len(result.rows) == 1
