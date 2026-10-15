from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    detail: str


class ErrorResponse(BaseModel):
    """Standard non-2xx envelope: {"error": {"code", "detail"}}."""

    error: ErrorBody


class HealthResponse(BaseModel):
    status: str = Field(description="ok when the process is serving")
    database: str = Field(description="ok | error: ...")
    chroma: str = Field(description="ok | error: ...")


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class Page(BaseModel):
    items: list[Any]
    meta: PageMeta
