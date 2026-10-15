from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

DocumentTypeLiteral = Literal["medicine", "patient"]


class DocumentOut(BaseModel):
    id: UUID
    doc_type: DocumentTypeLiteral
    filename: str
    status: Literal["uploaded", "processing", "indexed", "failed"]
    page_count: int | None = None
    chunk_count: int | None = None
    error: str | None = None
    created_at: datetime
    indexed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentListOut(BaseModel):
    items: list[DocumentOut]
