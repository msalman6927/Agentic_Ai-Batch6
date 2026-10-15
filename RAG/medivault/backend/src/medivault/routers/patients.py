from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import PatientEntry, parse_dob
from medivault.schemas.consultation import ConsultationListOut
from medivault.schemas.patient import (
    PatientCreate,
    PatientListOut,
    PatientOut,
    PatientUpdate,
)
from medivault.services import consultation_service, patient_service

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=PatientListOut)
async def list_patients(
    q: Annotated[str | None, Query(max_length=256)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PatientListOut:
    items, total = await patient_service.list_patients(q=q, limit=limit, offset=offset)
    return PatientListOut(
        items=[PatientOut.model_validate(item) for item in items], total=total
    )


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate) -> PatientOut:
    patient = await patient_service.create_patient(
        PatientEntry(**payload.model_dump(mode="json"))
    )
    return PatientOut.model_validate(patient)


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(patient_id: UUID) -> PatientOut:
    patient = await patient_service.get_patient(patient_id)
    return PatientOut.model_validate(patient)


@router.put("/{patient_id}", response_model=PatientOut)
async def update_patient(patient_id: UUID, payload: PatientUpdate) -> PatientOut:
    patient = await patient_service.get_patient(patient_id)
    updates = payload.model_dump(exclude_unset=True)
    if "dob" in updates:
        raw = updates["dob"]
        updates["dob"] = raw if raw is None else parse_dob(str(raw))
    for field, value in updates.items():
        setattr(patient, field, value)
    factory = get_session_factory()
    async with factory() as session:
        managed = await session.merge(patient)
        await session.commit()
        await session.refresh(managed)
        return PatientOut.model_validate(managed)


@router.get(
    "/{patient_id}/consultations",
    response_model=ConsultationListOut,
)
async def get_patient_consultations(patient_id: UUID) -> ConsultationListOut:
    await patient_service.get_patient(patient_id)
    consultations = await consultation_service.list_consultations(patient_id=patient_id)
    return ConsultationListOut(items=consultations)


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_patient(patient_id: UUID) -> None:
    await patient_service.delete_patient(patient_id)
