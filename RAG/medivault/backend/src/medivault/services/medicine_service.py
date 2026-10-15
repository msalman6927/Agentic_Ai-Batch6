from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select

from medivault.db.models import Medicine, MedicineInteraction
from medivault.dependencies import get_session_factory
from medivault.ingestion.extractor import MedicineEntry
from medivault.utils.errors import NotFoundError


async def list_medicines(
    *, q: str | None = None, limit: int = 50, offset: int = 0
) -> tuple[list[Medicine], int]:
    factory = get_session_factory()
    async with factory() as session:
        query = select(Medicine)
        if q:
            pattern = f"%{q.strip()}%"
            query = query.where(
                or_(
                    Medicine.generic_name.ilike(pattern),
                    func.coalesce(Medicine.brand_name, "").ilike(pattern),
                )
            )
        total = (
            await session.execute(select(func.count()).select_from(query.subquery()))
        ).scalar_one()
        rows = await session.scalars(
            query.order_by(Medicine.generic_name).limit(limit).offset(offset)
        )
        return list(rows), int(total)


async def get_medicine(medicine_id: UUID) -> Medicine:
    factory = get_session_factory()
    async with factory() as session:
        medicine = await session.get(Medicine, medicine_id)
        if medicine is None:
            raise NotFoundError(f"medicine {medicine_id} not found")
        return medicine


async def create_medicine(entry: MedicineEntry) -> Medicine:
    factory = get_session_factory()
    async with factory() as session:
        medicine = Medicine(
            id=uuid4(),
            generic_name=entry.generic_name,
            brand_name=entry.brand_name,
            drug_class=entry.drug_class,
            indications=entry.indications,
            dosage=entry.dosage,
            route=entry.route,
            contraindications=entry.contraindications,
            warnings=entry.warnings,
            side_effects=entry.side_effects,
        )
        session.add(medicine)
        await session.commit()
        await session.refresh(medicine)
        return medicine


async def replace_medicines_for_document(
    document_id: UUID, entries: list[MedicineEntry]
) -> int:
    """Delete prior rows sourced from this document, insert fresh + interactions."""
    factory = get_session_factory()
    async with factory() as session:
        old_ids = list(
            await session.scalars(
                select(Medicine.id).where(Medicine.source_document_id == document_id)
            )
        )
        if old_ids:
            await session.execute(
                delete(MedicineInteraction).where(
                    MedicineInteraction.medicine_a_id.in_(old_ids)
                    | MedicineInteraction.medicine_b_id.in_(old_ids)
                )
            )
            await session.execute(delete(Medicine).where(Medicine.id.in_(old_ids)))

        created: list[Medicine] = []
        for entry in entries:
            medicine = Medicine(
                id=uuid4(),
                generic_name=entry.generic_name,
                brand_name=entry.brand_name,
                drug_class=entry.drug_class,
                indications=entry.indications,
                dosage=entry.dosage,
                route=entry.route,
                contraindications=entry.contraindications,
                warnings=entry.warnings,
                side_effects=entry.side_effects,
                source_document_id=document_id,
            )
            session.add(medicine)
            created.append(medicine)
        await session.flush()

        for entry, medicine in zip(entries, created, strict=True):
            for interaction in entry.interactions:
                other = await _find_by_name(
                    session, interaction.with_medicine, exclude=medicine.id
                )
                if other is None:
                    continue
                session.add(
                    MedicineInteraction(
                        id=uuid4(),
                        medicine_a_id=medicine.id,
                        medicine_b_id=other.id,
                        severity=interaction.severity,
                        description=interaction.description,
                    )
                )
        await session.commit()
        return len(created)


async def _find_by_name(session, name: str, exclude: UUID | None = None):
    pattern = name.strip().lower()
    if not pattern:
        return None
    result = await session.scalars(
        select(Medicine).where(
            or_(
                func.lower(Medicine.generic_name) == pattern,
                func.lower(func.coalesce(Medicine.brand_name, "")) == pattern,
            )
        )
    )
    for medicine in result:
        if exclude is not None and medicine.id == exclude:
            continue
        return medicine
    return None


async def delete_medicine(medicine_id: UUID) -> None:
    factory = get_session_factory()
    async with factory() as session:
        medicine = await session.get(Medicine, medicine_id)
        if medicine is None:
            raise NotFoundError(f"medicine {medicine_id} not found")
        await session.delete(medicine)
        await session.commit()
