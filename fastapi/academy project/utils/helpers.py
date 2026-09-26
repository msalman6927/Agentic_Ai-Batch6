from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


async def get_or_404(
	session: AsyncSession,
	model: type[DeclarativeBase],
	record_id: int,
	resource_name: str,
) -> DeclarativeBase:
	record = await session.get(model, record_id)
	if record is None:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"{resource_name} with id {record_id} was not found",
		)
	return record


async def ensure_email_available(
	session: AsyncSession,
	model: type[DeclarativeBase],
	email: str,
	conflict_detail: str,
	excluded_id: int | None = None,
) -> None:
	stmt = select(model.id).where(model.email == email)
	if excluded_id is not None:
		stmt = stmt.where(model.id != excluded_id)
	result = await session.execute(stmt)
	if result.scalar_one_or_none() is not None:
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=conflict_detail,
		)
