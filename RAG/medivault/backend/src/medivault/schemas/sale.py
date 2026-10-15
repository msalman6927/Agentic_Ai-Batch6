from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class SaleOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    sale_date: date
    item_name: str
    quantity: int
    unit_price: float
    total: float


class SaleListOut(BaseModel):
    items: list[SaleOut]


class SalesUploadOut(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    filename: str
    row_count: int
    error_count: int
    errors: list[dict[str, Any]]


class SalesSummaryItem(BaseModel):
    item_name: str
    total_quantity: int
    total_revenue: float
    rows: int


class SalesSummaryOut(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    item_count: int
    total_revenue: float
    total_quantity: int
    items: list[SalesSummaryItem]
