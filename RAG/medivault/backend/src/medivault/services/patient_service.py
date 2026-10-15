from uuid import UUID, uuid4

from sqlalchemy import delete, func, select

from medivault.db.models import Patient
from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import PatientEntry, parse_dob
from medivault.utils.errors import NotFoundError


def _entry_to_patient(
    entry: PatientEntry, *, document_id: UUID | None = None
) -> Patient:
    return Patient(
        id=uuid4(),
        full_name=entry.full_name,
        aliases=entry.aliases or [],
        dob=parse_dob(entry.dob),
        gender=entry.gender,
        blood_group=entry.blood_group,
        allergies=entry.allergies or [],
        conditions=entry.conditions or [],
        notes=entry.notes,
        source_document_id=document_id,
    )


async def list_patients(
    *, q: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[Patient], int]:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Patient)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(Patient.full_name.ilike(pattern))
        total = (
            await session.execute(select(func.count()).select_from(query.subquery()))
        ).scalar_one()
        rows = await session.scalars(
            query.order_by(Patient.full_name).limit(limit).offset(offset)
        )
        return list(rows), int(total)


async def get_patient(patient_id: UUID) -> Patient:
    factory = get_session_factory()
    async with factory() as session:
        patient = await session.get(Patient, patient_id)
        if patient is None:
            raise NotFoundError(f"patient {patient_id} not found")
        return patient


async def create_patient(entry: PatientEntry) -> Patient:
    factory = get_session_factory()
    async with factory() as session:
        patient = _entry_to_patient(entry)
        session.add(patient)
        await session.commit()
        await session.refresh(patient)
        return patient


async def replace_patients_for_document(
    document_id: UUID, entries: list[PatientEntry]
) -> int:
    factory = get_session_factory()
    async with factory() as session:
        await session.execute(
            delete(Patient).where(Patient.source_document_id == document_id)
        )
        for entry in entries:
            session.add(_entry_to_patient(entry, document_id=document_id))
        await session.commit()
        return len(entries)


async def delete_patient(patient_id: UUID) -> None:
    factory = get_session_factory()
    async with factory() as session:
        patient = await session.get(Patient, patient_id)
        if patient is None:
            raise NotFoundError(f"patient {patient_id} not found")
        await session.delete(patient)
        await session.commit()
