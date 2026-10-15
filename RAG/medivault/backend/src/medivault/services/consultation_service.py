from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select

from medivault.db.models import Consultation
from medivault.dependencies import get_session_factory
from medivault.utils.errors import ConflictError, NotFoundError, ValidationFailure


def _validate_recommended(recommended: list[dict]) -> list[dict]:
    cleaned: list[dict] = []
    for item in recommended:
        name = (item.get("name") or item.get("medicine_name") or "").strip()
        if not name:
            raise ValidationFailure("each recommended item needs a medicine name")
        cleaned.append(
            {
                "medicine_id": item.get("medicine_id"),
                "name": name,
                "dose": item.get("dose"),
                "frequency": item.get("frequency"),
                "duration": item.get("duration"),
            }
        )
    return cleaned


async def create_draft(
    *,
    patient_id: UUID,
    chief_complaint: str | None,
    diagnosis: str | None,
    recommended: list[dict],
    notes: str | None = None,
    follow_up_date: date | None = None,
    confidence: float | None = None,
) -> Consultation:
    from medivault.db.models import Patient

    factory = get_session_factory()
    async with factory() as session:
        patient = await session.get(Patient, patient_id)
        if patient is None:
            raise NotFoundError(f"patient {patient_id} not found")
        consultation = Consultation(
            id=uuid4(),
            patient_id=patient_id,
            chief_complaint=chief_complaint,
            diagnosis=diagnosis,
            recommended=_validate_recommended(recommended),
            notes=notes,
            follow_up_date=follow_up_date,
            status="draft",
            confidence=confidence,
        )
        session.add(consultation)
        await session.commit()
        await session.refresh(consultation)
        return consultation


async def confirm(draft_id: UUID) -> Consultation:
    factory = get_session_factory()
    async with factory() as session:
        consultation = await session.get(Consultation, draft_id)
        if consultation is None:
            raise NotFoundError(f"consultation {draft_id} not found")
        if consultation.status == "committed":
            raise ConflictError(f"consultation {draft_id} already committed")
        if consultation.status == "cancelled":
            raise ConflictError(f"consultation {draft_id} was cancelled")
        consultation.status = "committed"
        await session.commit()
        await session.refresh(consultation)
        return consultation


async def cancel(draft_id: UUID) -> Consultation:
    factory = get_session_factory()
    async with factory() as session:
        consultation = await session.get(Consultation, draft_id)
        if consultation is None:
            raise NotFoundError(f"consultation {draft_id} not found")
        if consultation.status == "committed":
            raise ConflictError("committed consultations cannot be cancelled")
        consultation.status = "cancelled"
        await session.commit()
        await session.refresh(consultation)
        return consultation


async def get_consultation(consultation_id: UUID) -> Consultation:
    factory = get_session_factory()
    async with factory() as session:
        consultation = await session.get(Consultation, consultation_id)
        if consultation is None:
            raise NotFoundError(f"consultation {consultation_id} not found")
        return consultation


async def list_consultations(
    *, patient_id: UUID | None = None, status_filter: str | None = None
) -> list[Consultation]:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Consultation)
        if patient_id is not None:
            query = query.where(Consultation.patient_id == patient_id)
        if status_filter:
            query = query.where(Consultation.status == status_filter)
        rows = await session.scalars(
            query.order_by(Consultation.created_at.desc()).limit(100)
        )
        return list(rows)


async def get_patient_history(
    patient_id: UUID, *, limit: int = 10
) -> list[Consultation]:
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.scalars(
            select(Consultation)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.status == "committed",
            )
            .order_by(Consultation.created_at.desc())
            .limit(limit)
        )
        return list(rows)
