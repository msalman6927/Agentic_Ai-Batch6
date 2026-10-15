from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from medivault.schemas.consultation import (
    ConfirmRequest,
    ConsultationListOut,
    ConsultationOut,
    ManualConsultationIn,
    RecommendedItemOut,
)
from medivault.services import consultation_service

router = APIRouter(prefix="/consultations", tags=["consultations"])


def _to_out(consultation) -> ConsultationOut:
    out = ConsultationOut.model_validate(consultation)
    out.recommended = [
        RecommendedItemOut(**item) for item in (consultation.recommended or [])
    ]
    return out


@router.post("/confirm", response_model=ConsultationOut)
async def confirm_consultation(payload: ConfirmRequest) -> ConsultationOut:
    consultation = await consultation_service.confirm(payload.draft_id)
    return _to_out(consultation)


@router.post("/cancel", response_model=ConsultationOut)
async def cancel_consultation(payload: ConfirmRequest) -> ConsultationOut:
    consultation = await consultation_service.cancel(payload.draft_id)
    return _to_out(consultation)


@router.post("", response_model=ConsultationOut, status_code=status.HTTP_201_CREATED)
async def create_consultation(payload: ManualConsultationIn) -> ConsultationOut:
    draft = await consultation_service.create_draft(
        patient_id=payload.patient_id,
        chief_complaint=payload.chief_complaint,
        diagnosis=payload.diagnosis,
        recommended=[item.model_dump() for item in payload.recommended],
        notes=payload.notes,
        follow_up_date=payload.follow_up_date,
    )
    consultation = await consultation_service.confirm(draft.id)
    return _to_out(consultation)


@router.get("/{consultation_id}", response_model=ConsultationOut)
async def get_consultation(consultation_id: UUID) -> ConsultationOut:
    consultation = await consultation_service.get_consultation(consultation_id)
    return _to_out(consultation)


@router.get("", response_model=ConsultationListOut)
async def list_consultations(
    patient_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> ConsultationListOut:
    consultations = await consultation_service.list_consultations(
        patient_id=patient_id, status_filter=status_filter
    )
    return ConsultationListOut(items=[_to_out(item) for item in consultations])
