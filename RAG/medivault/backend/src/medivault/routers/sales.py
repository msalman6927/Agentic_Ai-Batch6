from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Query, UploadFile, status

from medivault.schemas.sale import (
    SaleListOut,
    SaleOut,
    SalesSummaryOut,
    SalesUploadOut,
)
from medivault.services import sales_service
from medivault.utils.errors import IngestError, ValidationFailure

router = APIRouter(prefix="/sales", tags=["sales"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post(
    "/upload", response_model=SalesUploadOut, status_code=status.HTTP_201_CREATED
)
async def upload_sales(file: Annotated[UploadFile, File()]) -> SalesUploadOut:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise IngestError("only .csv files are accepted")
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValidationFailure("CSV exceeds the 10MB limit")
    upload = await sales_service.upload_sales_csv(
        filename=file.filename, content=content
    )
    return SalesUploadOut.model_validate(upload)


@router.get("", response_model=SaleListOut)
async def list_sales(
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    item_name: str | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> SaleListOut:
    rows = await sales_service.list_sales(
        from_date=from_date, to_date=to_date, item_name=item_name, limit=limit
    )
    return SaleListOut(items=[SaleOut.model_validate(row) for row in rows])


@router.get("/summary", response_model=SalesSummaryOut)
async def sales_summary(
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
    item_name: str | None = None,
) -> SalesSummaryOut:
    data = await sales_service.sales_summary(
        from_date=from_date, to_date=to_date, item_name=item_name
    )
    return SalesSummaryOut.model_validate(data)


@router.delete("/uploads/{upload_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_upload(upload_id: UUID) -> None:
    await sales_service.delete_upload(upload_id)
