from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select

from medivault.db.models import Sale, SalesUpload
from medivault.dependencies import get_session_factory
from medivault.ingestion.csv_loader import parse_sales_csv
from medivault.utils.errors import ValidationFailure


async def upload_sales_csv(*, filename: str, content: bytes) -> SalesUpload:
    parsed = parse_sales_csv(content)
    if not parsed.rows and parsed.errors:
        raise ValidationFailure(
            "CSV rejected: "
            + "; ".join(f"row {e['row']}: {e['error']}" for e in parsed.errors[:5])
        )
    factory = get_session_factory()
    async with factory() as session:
        upload = SalesUpload(
            id=uuid4(),
            filename=filename,
            row_count=len(parsed.rows),
            error_count=len(parsed.errors),
            errors=parsed.errors or [],
        )
        session.add(upload)
        await session.flush()
        for row in parsed.rows:
            session.add(
                Sale(
                    id=uuid4(),
                    sale_date=row.sale_date,
                    item_name=row.item_name,
                    quantity=row.quantity,
                    unit_price=row.unit_price,
                    total=row.total,
                    upload_id=upload.id,
                )
            )
        await session.commit()
        await session.refresh(upload)
        return upload


async def list_sales(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    item_name: str | None = None,
    limit: int = 200,
) -> list[Sale]:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Sale)
        if from_date is not None:
            query = query.where(Sale.sale_date >= from_date)
        if to_date is not None:
            query = query.where(Sale.sale_date <= to_date)
        if item_name:
            query = query.where(Sale.item_name.ilike(f"%{item_name.strip()}%"))
        rows = await session.scalars(query.order_by(Sale.sale_date.desc()).limit(limit))
        return list(rows)


async def sales_summary(
    *,
    from_date: date | None = None,
    to_date: date | None = None,
    item_name: str | None = None,
) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        query = select(
            Sale.item_name,
            func.sum(Sale.quantity).label("total_quantity"),
            func.sum(Sale.total).label("total_revenue"),
            func.count(Sale.id).label("rows"),
        )
        if from_date is not None:
            query = query.where(Sale.sale_date >= from_date)
        if to_date is not None:
            query = query.where(Sale.sale_date <= to_date)
        if item_name:
            query = query.where(Sale.item_name.ilike(f"%{item_name.strip()}%"))
        query = query.group_by(Sale.item_name).order_by(func.sum(Sale.total).desc())
        rows = (await session.execute(query)).all()
        items: list[dict] = [
            {
                "item_name": row[0],
                "total_quantity": int(row[1] or 0),
                "total_revenue": float(row[2] or Decimal("0")),
                "rows": int(row[3]),
            }
            for row in rows
        ]
        total_revenue = round(sum(float(item["total_revenue"]) for item in items), 2)
        total_quantity = sum(int(item["total_quantity"]) for item in items)
        return {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "item_count": len(items),
            "total_revenue": total_revenue,
            "total_quantity": total_quantity,
            "items": items,
        }


async def delete_upload(upload_id: UUID) -> None:
    from sqlalchemy import delete as sa_delete

    factory = get_session_factory()
    async with factory() as session:
        upload = await session.get(SalesUpload, upload_id)
        if upload is None:
            from medivault.utils.errors import NotFoundError

            raise NotFoundError(f"upload {upload_id} not found")
        await session.execute(sa_delete(Sale).where(Sale.upload_id == upload_id))
        await session.delete(upload)
        await session.commit()
