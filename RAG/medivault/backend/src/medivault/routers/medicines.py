from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import MedicineEntry
from medivault.schemas.medicine import (
    MedicineCreate,
    MedicineListOut,
    MedicineOut,
    MedicineUpdate,
)
from medivault.services import medicine_service

router = APIRouter(prefix="/medicines", tags=["medicines"])


@router.get("", response_model=MedicineListOut)
async def list_medicines(
    q: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MedicineListOut:
    items, total = await medicine_service.list_medicines(
        q=q, limit=limit, offset=offset
    )
    return MedicineListOut(
        items=[MedicineOut.model_validate(item) for item in items], total=total
    )


@router.post("", response_model=MedicineOut, status_code=status.HTTP_201_CREATED)
async def create_medicine(payload: MedicineCreate) -> MedicineOut:
    medicine = await medicine_service.create_medicine(
        MedicineEntry(**payload.model_dump())
    )
    return MedicineOut.model_validate(medicine)


@router.get("/{medicine_id}", response_model=MedicineOut)
async def get_medicine(medicine_id: UUID) -> MedicineOut:
    medicine = await medicine_service.get_medicine(medicine_id)
    return MedicineOut.model_validate(medicine)


@router.put("/{medicine_id}", response_model=MedicineOut)
async def update_medicine(medicine_id: UUID, payload: MedicineUpdate) -> MedicineOut:
    medicine = await medicine_service.get_medicine(medicine_id)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(medicine, field, value)
    factory = get_session_factory()
    async with factory() as session:
        managed = await session.merge(medicine)
        await session.commit()
        await session.refresh(managed)
        return MedicineOut.model_validate(managed)


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_medicine(medicine_id: UUID) -> None:
    await medicine_service.delete_medicine(medicine_id)
